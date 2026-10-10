/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // 主色：石墨墨绿。饱和度比 indigo 低、明度更沉，
        // 用于按钮、选中态、链接等界面主结构。
        brand: {
          50: '#F1F6F5',
          100: '#E0EDEA',
          200: '#C2DBD5',
          300: '#94BFB6',
          400: '#5F9E93',
          500: '#3C8177',
          600: '#2C675E',
          700: '#24534C',
          800: '#1D423D',
          900: '#15312D',
          950: '#0A1C1A',
        },
        // 强调色：琥珀红陶。只作小面积点缀（Logo 副块、状态点、高亮），
        // 不用来铺大面积按钮，避免界面跳。
        accent: {
          50: '#FDF5EC',
          100: '#FAE8D3',
          200: '#F3CDA6',
          300: '#E9AC72',
          400: '#DE8C4A',
          500: '#CE7033',
          600: '#B45A28',
          700: '#934523',
          800: '#773920',
          900: '#62331E',
        },
        // 兼容旧名：少量历史样式仍引用 primary-*，映射到主色
        primary: {
          DEFAULT: '#2C675E',
          50: '#F1F6F5',
          100: '#E0EDEA',
          200: '#C2DBD5',
          300: '#94BFB6',
          400: '#5F9E93',
          500: '#3C8177',
          600: '#2C675E',
          700: '#24534C',
          800: '#1D423D',
          900: '#15312D',
        },
      },
      borderRadius: {
        'xl': '0.75rem',
        '2xl': '1rem',
        '3xl': '1.5rem',
      },
      boxShadow: {
        'soft': '0 2px 8px -2px rgba(0, 0, 0, 0.05), 0 4px 16px -2px rgba(0, 0, 0, 0.05)',
        'medium': '0 4px 12px -2px rgba(0, 0, 0, 0.08), 0 8px 24px -4px rgba(0, 0, 0, 0.08)',
        'large': '0 8px 24px -4px rgba(0, 0, 0, 0.1), 0 16px 48px -8px rgba(0, 0, 0, 0.1)',
      },
      animation: {
        'fade-in': 'fadeIn 0.2s ease-out',
        'slide-up': 'slideUp 0.3s ease-out',
        'slide-down': 'slideDown 0.3s ease-out',
      },
      fontFamily: {
        sans: ['-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'Helvetica Neue', 'Arial', 'sans-serif'],
        mono: ['SF Mono', 'Monaco', 'Inconsolata', 'Fira Code', 'monospace'],
      },
    },
  },
  plugins: [],
}
