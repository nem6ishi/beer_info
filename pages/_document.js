import { Html, Head, Main, NextScript } from 'next/document'

export default function Document() {
    return (
        <Html lang="ja">
            <Head>
                <link rel="manifest" href="/manifest.json" />
                <link rel="apple-touch-icon" href="/icon-192.png" />
                <meta name="theme-color" content="#ffffff" />
                <meta name="apple-mobile-web-app-capable" content="yes" />
                <meta name="apple-mobile-web-app-status-bar-style" content="default" />
                <meta name="apple-mobile-web-app-title" content="BeerAlert" />
            </Head>
            <body>
                <div id="safari-debug-log" style={{
                    position: 'fixed', bottom: '150px', left: 0, right: 0,
                    height: '150px', overflowY: 'auto',
                    background: 'rgba(50,0,0,0.9)', color: '#fff',
                    fontSize: '10px', padding: '5px', zIndex: 10000,
                    pointerEvents: 'none'
                }}>
                    <div>Global Debugger Active.</div>
                </div>
                <script dangerouslySetInnerHTML={{
                    __html: `
                        // Print UA immediately
                        var log = document.getElementById('safari-debug-log');
                        if (log) {
                            var div = document.createElement('div');
                            div.textContent = 'UA: ' + navigator.userAgent;
                            log.appendChild(div);
                        }

                        window.onerror = function(msg, url, line, col, error) {
                            if (log) {
                                var div = document.createElement('div');
                                div.style.borderBottom = '1px solid #666';
                                div.style.padding = '2px';
                                div.style.color = '#ff9999';
                                div.textContent = 'Global Error: ' + msg + ' (' + line + ':' + col + ')';
                                log.appendChild(div);
                            }
                        };
                        window.onunhandledrejection = function(event) {
                             if (log) {
                                var div = document.createElement('div');
                                div.style.borderBottom = '1px solid #666';
                                div.style.padding = '2px';
                                div.style.color = '#ff9999';
                                div.textContent = 'Unhandled Rejection: ' + event.reason;
                                log.appendChild(div);
                             }
                        };
                    `
                }} />
                <Main />
                <NextScript />
            </body>
        </Html>
    )
}
