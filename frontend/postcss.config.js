// 用 CJS 而不是 ESM：package.json 没有 "type": "module"，Node 18（CI 用的版本）
// 不认识 `export default`，会报 SyntaxError: Unexpected token 'export'，
// 表现为 "Failed to load PostCSS config"。本地 Node 20+ 会自动识别 ESM，
// 所以这个问题只在 CI 暴露。
module.exports = {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}
