import contextlib
import importlib.util
import io
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class FakeHTTPResponse:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.payload


MODULE_PATH = Path(__file__).with_name("youtube_transcript.py")
spec = importlib.util.spec_from_file_location("youtube_transcript_skill", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


NATIVE_RESPONSE = {
    "lang": "en",
    "availableLangs": ["en", "de"],
    "content": [
        {"text": "Hello", "offset": 0, "duration": 1000},
        {"text": "World", "offset": 1200, "duration": 800},
    ],
}


class YouTubeTranscriptSkillTests(unittest.TestCase):
    def test_accepts_supported_urls_and_rejects_other_hosts(self):
        self.assertEqual(module.video_id_from_input("https://youtu.be/dQw4w9WgXcQ"), "dQw4w9WgXcQ")
        self.assertEqual(module.video_id_from_input("https://www.youtube.com/shorts/dQw4w9WgXcQ"), "dQw4w9WgXcQ")
        with self.assertRaises(ValueError):
            module.video_id_from_input("https://example.com/watch?v=dQw4w9WgXcQ")

    def test_safe_title_prevents_path_components(self):
        title = module.safe_title("../private/secret: video")
        self.assertNotIn("/", title)
        self.assertNotIn("..", title)

    def test_requires_supadata_key(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "SUPADATA_API_KEY"):
                module.require_api_key()

    def test_native_response_requires_caption_segments(self):
        with self.assertRaisesRegex(RuntimeError, "Generated transcription is disabled"):
            module.transcript_chunks({"content": [], "availableLangs": ["en"]})

    def test_persistence_is_private_and_keeps_timestamps(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(module, "private_output_dir", return_value=Path(directory)):
            transcript, sidecar, language = module.write_transcript("dQw4w9WgXcQ", {"title": "A title"}, NATIVE_RESPONSE)
            self.assertTrue(transcript.exists())
            self.assertTrue(sidecar.exists())
            self.assertEqual(language, "en")
            self.assertEqual(stat.S_IMODE(transcript.stat().st_mode), 0o600)
            metadata = json.loads(sidecar.read_text())
            self.assertEqual(metadata["video_id"], "dQw4w9WgXcQ")
            self.assertEqual(metadata["transcript_mode"], "native")
            self.assertEqual(metadata["segment_count"], 2)
            self.assertIn("A title_dQw4w9WgXcQ", transcript.name)
            self.assertIn("[00:00:01] World", transcript.read_text())

    def test_202_job_is_polled_until_native_captions_complete(self):
        queued = {"status": "queued"}
        completed = {"status": "completed", **NATIVE_RESPONSE}
        with patch.object(module, "require_api_key", return_value="test-key"), patch.object(
            module,
            "supadata_json",
            side_effect=[(202, {"jobId": "job/123"}), (200, queued), (200, completed)],
        ) as request, patch.object(module.time, "sleep") as sleep:
            response, job_id = module.supadata_transcript("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "en")
            self.assertIsNone(response)
            response = module.poll_supadata_job(job_id, "test-key", 30)
        self.assertEqual(response, completed)
        self.assertEqual(job_id, "job/123")
        self.assertEqual(request.call_count, 3)
        self.assertTrue(request.call_args_list[1].args[0].endswith("/job%2F123"))
        sleep.assert_called_once_with(module.SUPADATA_POLL_INTERVAL_SECONDS)

    def test_pending_job_is_saved_and_can_be_resumed_without_resubmitting(self):
        pending = {"status": "queued"}
        completed = {"status": "completed", **NATIVE_RESPONSE}
        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as directory, patch.object(module, "private_output_dir", return_value=Path(directory)), patch.object(
            module, "metadata", return_value={"video_id": "dQw4w9WgXcQ", "title": "A title"}
        ), patch.dict(os.environ, {"SUPADATA_API_KEY": "test-key"}, clear=True), patch.object(
            module, "supadata_json", side_effect=[(202, {"jobId": "job/123"}), (200, pending)]
        ), patch.object(module.sys, "argv", ["youtube_transcript.py", "dQw4w9WgXcQ", "--no-summary", "--wait-seconds", "0"]), contextlib.redirect_stderr(stderr), contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(module.main(), 0)
            first = json.loads(output.getvalue())
            self.assertEqual(first["status"], "pending")
            self.assertIn("--no-summary", first["next_command"])
            state_path = first["job_state_path"]

            with patch.object(module, "supadata_json", return_value=(200, completed)) as poll, patch.object(
                module.sys, "argv", ["youtube_transcript.py", "--job-state", state_path, "--wait-seconds", "1"]
            ), contextlib.redirect_stdout(io.StringIO()) as resumed_output:
                self.assertEqual(module.main(), 0)
            second = json.loads(resumed_output.getvalue())
            self.assertEqual(second["status"], "partial")
            self.assertTrue(Path(second["transcript_path"]).exists())
        self.assertEqual(poll.call_count, 1)
        self.assertNotIn("transcript?", poll.call_args.args[0])

    def test_poll_with_no_remaining_budget_returns_pending_without_a_request(self):
        with patch.object(module, "supadata_json") as request:
            self.assertIsNone(module.poll_supadata_job("job/123", "test-key", 0))
        request.assert_not_called()

    def test_retryable_poll_failure_at_deadline_returns_pending(self):
        failure = module.SupadataRequestError("temporary", retryable=True)
        with patch.object(module, "supadata_json", side_effect=failure), patch.object(
            module.time, "monotonic", side_effect=[0, 0, 1]
        ):
            self.assertIsNone(module.poll_supadata_job("job/123", "test-key", 1))

    def test_openrouter_requires_key(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "OPENROUTER_API_KEY"):
                module.openrouter("hello", module.DEFAULT_MODEL)

    def test_missing_openrouter_key_stops_before_supadata_request(self):
        stderr = io.StringIO()
        with patch.dict(os.environ, {"SUPADATA_API_KEY": "test-key"}, clear=True), patch.object(
            module.sys, "argv", ["youtube_transcript.py", "dQw4w9WgXcQ"]
        ), patch.object(module, "supadata_transcript") as supadata_request, contextlib.redirect_stderr(stderr):
            self.assertEqual(module.main(), 1)
        supadata_request.assert_not_called()
        self.assertIn("OPENROUTER_API_KEY", stderr.getvalue())

    def test_openrouter_sets_reasoning_budget_for_visible_summary(self):
        response = {"choices": [{"message": {"content": "A summary"}}]}
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}), patch.object(
            module.urllib.request, "urlopen", return_value=FakeHTTPResponse(response)
        ) as urlopen:
            self.assertEqual(module.openrouter("hello", module.DEFAULT_MODEL), ("A summary", module.DEFAULT_MODEL))
        payload = json.loads(urlopen.call_args.args[0].data)
        self.assertEqual(payload["max_tokens"], 4000)
        self.assertEqual(payload["reasoning"], {"effort": "low", "exclude": True})
        self.assertNotIn("models", payload)

    def test_openrouter_sends_ordered_model_fallbacks(self):
        response = {"model": "fallback/two", "choices": [{"message": {"content": "A summary"}}]}
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}), patch.object(
            module.urllib.request, "urlopen", return_value=FakeHTTPResponse(response)
        ) as urlopen:
            content, used_model = module.openrouter("hello", "primary/one", ("fallback/one", "fallback/two"))
        self.assertEqual((content, used_model), ("A summary", "fallback/two"))
        payload = json.loads(urlopen.call_args.args[0].data)
        self.assertEqual(payload["model"], "primary/one")
        self.assertEqual(payload["models"], ["fallback/one", "fallback/two"])

    def test_openrouter_rejects_empty_visible_content(self):
        response = {"choices": [{"message": {"content": None, "reasoning": "internal"}}]}
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}), patch.object(
            module.urllib.request, "urlopen", return_value=FakeHTTPResponse(response)
        ):
            with self.assertRaisesRegex(RuntimeError, "no visible summary content"):
                module.openrouter("hello", module.DEFAULT_MODEL)


if __name__ == "__main__":
    unittest.main()
