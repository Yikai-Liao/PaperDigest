#!/bin/bash
git submodule update --init --recursive
cd website
pnpm install
pnpm run build