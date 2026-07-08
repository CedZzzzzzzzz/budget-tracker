module.exports = {
  content: [
    "./index.html",
    "./src/**/*.{js,jsx,ts,tsx}"
  ],
  darkMode: ['selector', '[data-theme="dark"]'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      colors: {
        brand: {
          void: '#10002b',
          deep: '#240046',
          accent: '#3c096c',
          bright: '#7b2cbf',
          glow: '#9d4edd',
          dirty: '#ddd8d0',
          muted: '#a89f94',
        },
      },
      boxShadow: {
        modal: '0 0 0 1px rgba(157, 78, 221, 0.15), 0 0 60px rgba(123, 44, 191, 0.25), 0 25px 50px rgba(0, 0, 0, 0.5)',
        'modal-lg': '0 0 0 1px rgba(157, 78, 221, 0.25), 0 0 100px rgba(123, 44, 191, 0.2), 0 0 40px rgba(157, 78, 221, 0.15), 0 25px 60px rgba(0, 0, 0, 0.6)',
      },
    },
  },
  plugins: [],
};
