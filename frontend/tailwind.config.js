/** @type {import('tailwindcss').Config} */
module.exports = {
    content: [
        "./templates/**/*.{html,js}",
        "./static/**/*.{html,js}"
    ],
    theme: {
        extend: {
            fontFamily: {
                sans: ['"Plus Jakarta Sans"', 'sans-serif'],
                display: ['"Outfit"', 'sans-serif'],
            },
            colors: {
                brand: {
                    50: '#f0fdfa',
                    100: '#ccfbf1',
                    500: '#0d9488',
                    600: '#0f766e',
                    900: '#0f172a',
                },
                accent: {
                    400: '#f59e0b',
                    500: '#f97316',
                },
                teal: {
                    DEFAULT: '#0d9488',
                    light: '#14b8a6',
                    soft: '#f0fdfa',
                },
                navy: {
                    DEFAULT: '#0f172a',
                    light: '#1e293b',
                    soft: '#334155',
                },
                yellow: {
                    DEFAULT: '#f59e0b',
                    light: '#fbbf24',
                    soft: '#fef3c7',
                }
            },
            animation: {
                'blob': 'blob 7s infinite',
                'float': 'float 6s ease-in-out infinite',
                'scroll': 'scroll 20s linear infinite',
            },
            keyframes: {
                blob: {
                    '0%': { transform: 'translate(0px, 0px) scale(1)' },
                    '33%': { transform: 'translate(30px, -50px) scale(1.1)' },
                    '66%': { transform: 'translate(-20px, 20px) scale(0.9)' },
                    '100%': { transform: 'translate(0px, 0px) scale(1)' },
                },
                float: {
                    '0%, 100%': { transform: 'translateY(0)' },
                    '50%': { transform: 'translateY(-20px)' },
                },
                scroll: {
                    '0%': { transform: 'translateX(0)' },
                    '100%': { transform: 'translateX(-100%)' },
                }
            }
        }
    },
    plugins: [],
}
