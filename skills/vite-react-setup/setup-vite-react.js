#!/usr/bin/env node

/**
 * Automated setup script for Vite + React + TypeScript + Tailwind v4 + shadcn/ui + Vitest
 * Usage: node setup-vite-react.js [project-name]
 */

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const projectName = process.argv[2] || 'my-app';

console.log(`🚀 Setting up ${projectName}...`);

const run = (command, options = {}) => {
  console.log(`\n▶️  ${command}`);
  try {
    execSync(command, { stdio: 'inherit', ...options });
  } catch (error) {
    console.error(`❌ Failed to execute: ${command}`);
    process.exit(1);
  }
};

const writeFile = (filePath, content) => {
  console.log(`\n📝 Writing ${filePath}`);
  fs.writeFileSync(filePath, content.trim() + '\n');
};

// Step 1: Create Vite project
console.log('\n📦 Step 1: Creating Vite project...');
run(`npm create vite@latest ${projectName} -- --template react-ts`);

// Change to project directory
process.chdir(projectName);

// Step 2: Install base dependencies
console.log('\n📦 Step 2: Installing base dependencies...');
run('npm install');

// Step 3: Install Tailwind CSS v4
console.log('\n📦 Step 3: Installing Tailwind CSS v4...');
run('npm install tailwindcss @tailwindcss/vite');

// Step 4: Install shadcn/ui dependencies
console.log('\n📦 Step 4: Installing shadcn/ui dependencies...');
run('npm install -D @types/node');
run('npm install class-variance-authority clsx tailwind-merge');

// Step 5: Install Vitest
console.log('\n📦 Step 5: Installing Vitest...');
run('npm install -D vitest @vitest/ui jsdom @testing-library/react @testing-library/jest-dom');

// Step 6: Update vite.config.ts
console.log('\n⚙️  Step 6: Configuring Vite...');
const viteConfig = `/// <reference types="vitest/config" />
import path from "path"
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [
    tailwindcss(),
    react(),
  ],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
  },
})`;
writeFile('vite.config.ts', viteConfig);

// Step 7: Update tsconfig.json
console.log('\n⚙️  Step 7: Configuring TypeScript...');
const tsconfigPath = 'tsconfig.json';
const tsconfig = JSON.parse(fs.readFileSync(tsconfigPath, 'utf8'));
tsconfig.compilerOptions = tsconfig.compilerOptions || {};
tsconfig.compilerOptions.baseUrl = '.';
tsconfig.compilerOptions.paths = { '@/*': ['./src/*'] };
writeFile(tsconfigPath, JSON.stringify(tsconfig, null, 2));

// Step 8: Update src/index.css
console.log('\n⚙️  Step 8: Configuring Tailwind CSS...');
const indexCss = '@import "tailwindcss";';
writeFile('src/index.css', indexCss);

// Step 9: Create vite-env.d.ts
console.log('\n⚙️  Step 9: Creating Vite environment types...');
const viteEnv = '/// <reference types="vite/client" />';
writeFile('src/vite-env.d.ts', viteEnv);

// Step 10: Update package.json scripts
console.log('\n⚙️  Step 10: Updating package.json scripts...');
const packageJsonPath = 'package.json';
const packageJson = JSON.parse(fs.readFileSync(packageJsonPath, 'utf8'));
packageJson.scripts = packageJson.scripts || {};
packageJson.scripts.test = 'vitest';
packageJson.scripts['test:ui'] = 'vitest --ui';
writeFile(packageJsonPath, JSON.stringify(packageJson, null, 2));

// Step 11: Initialize shadcn/ui (with defaults)
console.log('\n⚙️  Step 11: Initializing shadcn/ui...');
console.log('⚠️  Running shadcn init with defaults...');
run('npx shadcn@latest init -d');

// Step 12: Verify build
console.log('\n🔨 Step 12: Testing build...');
run('npm run build');

console.log('\n✅ Setup complete!');
console.log('\n📋 Next steps:');
console.log(`   cd ${projectName}`);
console.log('   npm run dev          # Start development server');
console.log('   npm run build        # Build for production');
console.log('   npm run test         # Run tests');
console.log('   npm run test:ui      # Run tests with UI');
console.log('\n🎨 Add components:');
console.log('   npx shadcn@latest add button card');
