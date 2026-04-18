import type { AppProps } from 'next/app'
import '../public/style.css'
import '../public/pagination.css'

export default function App({ Component, pageProps }: AppProps) {
    return <Component {...pageProps} />
}
