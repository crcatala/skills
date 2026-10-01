/**
 * Shared dependency management utilities for skills.
 * 
 * Provides automatic dependency checking and installation
 * to ensure skills work on first run without manual setup.
 */

import fs from 'fs';
import path from 'path';
import { execSync, spawnSync } from 'child_process';

/**
 * Ensure dependencies are installed for a skill.
 * 
 * Checks if package.json exists but node_modules is missing,
 * and auto-installs dependencies if needed. After installation,
 * re-executes the current script so newly installed modules can be resolved.
 * 
 * @param {string} skillDir - Path to the skill directory (use import.meta.dirname)
 * @returns {boolean} true if deps are ready (never returns false - exits on failure)
 * 
 * @example
 * // At the top of your skill script:
 * import { ensureDeps } from './lib/deps.js';
 * ensureDeps(import.meta.dirname);
 */
export function ensureDeps(skillDir) {
  const pkgPath = path.join(skillDir, 'package.json');
  const nmPath = path.join(skillDir, 'node_modules');
  
  // No package.json = no deps needed
  if (!fs.existsSync(pkgPath)) {
    return true;
  }
  
  // node_modules exists = deps already installed
  if (fs.existsSync(nmPath)) {
    return true;
  }
  
  // Need to install deps
  const skillName = path.basename(skillDir);
  console.error(`[${skillName}] Installing dependencies (first-time setup)...`);
  
  try {
    // Try bun first (faster), fall back to npm
    const hasBun = (() => {
      try {
        execSync('which bun', { stdio: 'ignore' });
        return true;
      } catch {
        return false;
      }
    })();
    
    const cmd = hasBun ? 'bun install' : 'npm install';
    execSync(cmd, { 
      cwd: skillDir, 
      stdio: ['ignore', 'pipe', 'pipe'],
      timeout: 60000 // 60s timeout
    });
    
    console.error(`[${skillName}] Dependencies installed. Re-running...\n`);
    
    // Re-execute the current script with same args
    // This is needed because the module resolver has already cached "not found"
    const runtime = process.argv[0];
    const script = process.argv[1];
    const args = process.argv.slice(2);
    
    const result = spawnSync(runtime, [script, ...args], {
      stdio: 'inherit',
      cwd: process.cwd()
    });
    
    // Exit with the child's exit code
    process.exit(result.status || 0);
    
  } catch (error) {
    console.error(`\nError: Failed to install dependencies for ${skillName}.`);
    console.error(`\nPlease run manually:`);
    console.error(`  cd ${skillDir}`);
    console.error(`  bun install   # or: npm install\n`);
    
    if (error.message) {
      console.error(`Details: ${error.message}`);
    }
    
    process.exit(1);
  }
}

/**
 * Check if dependencies are installed (without auto-installing).
 * 
 * @param {string} skillDir - Path to the skill directory
 * @returns {{ needed: boolean, installed: boolean }} Status of dependencies
 */
export function checkDeps(skillDir) {
  const pkgPath = path.join(skillDir, 'package.json');
  const nmPath = path.join(skillDir, 'node_modules');
  
  const needed = fs.existsSync(pkgPath);
  const installed = fs.existsSync(nmPath);
  
  return { needed, installed };
}
