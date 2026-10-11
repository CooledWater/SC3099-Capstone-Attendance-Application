module.exports = {
  root: true,
  extends: 'next/core-web-vitals',
  parserOptions: {
    babelOptions: {
      // Resolve from this frontend even when the editor runs ESLint at the repo root.
      presets: [require.resolve('next/babel')],
    },
  },
  settings: {
    next: { rootDir: __dirname },
  },
};
