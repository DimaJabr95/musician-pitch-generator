import type { Config } from "jest";
import nextJest from "next/jest.js";

// next/jest wires up the TypeScript/JSX transform and Next.js settings for us.
const createJestConfig = nextJest({ dir: "./" });

const config: Config = {
  testEnvironment: "jsdom",
  setupFilesAfterEnv: ["<rootDir>/jest.setup.ts"],
};

export default createJestConfig(config);
