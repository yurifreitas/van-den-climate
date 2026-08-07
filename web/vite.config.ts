import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
// `base` precisa ser o subcaminho do GitHub Pages (/van-den-climate/) porque
// o site nao fica na raiz do dominio: sem isso todo asset e todo fetch do
// snapshot apontariam para yurifreitas.github.io/assets/... e dariam 404.
// Em dev e em qualquer deploy na raiz, fica '/'.
// Definido por env para nao travar o nome do repositorio dentro do codigo.
export default defineConfig({
  base: process.env.VITE_BASE ?? '/',
  plugins: [react()],
  server: {
    // Portas proprias do projeto, nao as default (5173/8000): as default
    // colidem com qualquer outro projeto aberto na maquina e o sintoma e
    // confuso — o front sobe, mas conversa com a API errada.
    port: 5931,
    strictPort: true, // falhar alto e melhor que subir numa porta surpresa
    proxy: {
      // Proxy /api -> API FastAPI local (docs/API_CONTRACT.md, base /api/v1).
      // Em dev sem a API rodando, MSW intercepta antes do fetch sair (main.tsx).
      '/api': {
        target: 'http://127.0.0.1:8437',
        changeOrigin: true,
      },
    },
  },
})
