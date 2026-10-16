export function WineArtwork() {
  return (
    <>
      <div className="wine-light-art" aria-hidden="true">
        <svg preserveAspectRatio="none" viewBox="0 0 1600 900">
          <defs>
            <linearGradient id="wine-streak" x1="0" x2="1">
              <stop offset="0" stopColor="#9b2552" stopOpacity=".22" />
              <stop offset=".42" stopColor="#fff" stopOpacity=".93" />
              <stop offset=".61" stopColor="#b83e72" stopOpacity=".90" />
              <stop offset="1" stopColor="#aa315f" stopOpacity=".15" />
            </linearGradient>
            <filter id="wine-glow"><feGaussianBlur stdDeviation="6" /></filter>
          </defs>
          <path d="M -100 190 C 260 360 480 400 1700 585" stroke="url(#wine-streak)" strokeWidth="6" filter="url(#wine-glow)" fill="none" />
          <path d="M -100 190 C 260 360 480 400 1700 585" stroke="url(#wine-streak)" strokeWidth="2" fill="none" />
          <path d="M -100 510 C 470 350 620 240 1700 540" stroke="#ad386c" strokeOpacity=".44" strokeWidth="1.3" fill="none" />
          <path d="M -100 600 C 350 650 700 465 1700 360" stroke="url(#wine-streak)" strokeOpacity=".5" strokeWidth="1.1" fill="none" />
          <path d="M -100 180 C 200 260 490 370 1700 530" stroke="#b83767" strokeOpacity=".25" strokeWidth="80" filter="url(#wine-glow)" fill="none" />
        </svg>
      </div>
      <div className="wine-art-a" aria-hidden="true">
        <svg viewBox="0 0 470 560">
          <defs>
            <linearGradient id="wine-a-dark" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0" stopColor="#e9b7c9" stopOpacity=".42" />
              <stop offset=".5" stopColor="#691135" stopOpacity=".18" />
              <stop offset="1" stopColor="#a72c60" stopOpacity=".62" />
            </linearGradient>
            <linearGradient id="wine-a-light" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0" stopColor="#fff" stopOpacity=".96" />
              <stop offset=".5" stopColor="#f7b8d0" stopOpacity=".42" />
              <stop offset="1" stopColor="#d2789e" stopOpacity=".2" />
            </linearGradient>
          </defs>
          <path className="outer" fillRule="evenodd" d="M217 15 L285 15 L465 530 L360 530 L315 393 L175 393 L130 530 L22 530 Z M244 149 L193 308 L294 308 Z" />
          <path d="M216 15 L285 15 L465 530" stroke="#df8fac" strokeWidth="1" opacity=".5" fill="none" />
        </svg>
      </div>
    </>
  );
}
