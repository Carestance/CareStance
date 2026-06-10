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
                    50: '#f0fdf4',
                    100: '#dcfce7',
                    500: '#0d9488',
                    600: '#0f766e',
                    900: '#001f3f',
                },
                accent: {
                    400: '#fbbf24',
                    500: '#ff8c00',
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
