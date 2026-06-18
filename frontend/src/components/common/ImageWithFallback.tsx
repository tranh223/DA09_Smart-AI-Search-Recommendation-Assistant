import { useState, type ImgHTMLAttributes } from 'react';

type Props = ImgHTMLAttributes<HTMLImageElement>;

const FALLBACK_SVG =
  'data:image/svg+xml;utf8,' +
  encodeURIComponent(`
    <svg xmlns="http://www.w3.org/2000/svg" width="800" height="600" viewBox="0 0 800 600">
      <rect width="800" height="600" fill="#F0ECE4"/>
      <circle cx="400" cy="250" r="58" fill="#DCD5C8"/>
      <path d="M190 460l145-165 95 105 70-80 110 140H190z" fill="#C9C0B2"/>
      <text x="400" y="525" text-anchor="middle" font-family="Arial, sans-serif" font-size="28" fill="#6E6A63">
        Image unavailable
      </text>
    </svg>
  `);

export function ImageWithFallback({ src, alt = '', onError, ...props }: Props) {
  const [fallback, setFallback] = useState(false);

  return (
    <img
      {...props}
      src={fallback || !src ? FALLBACK_SVG : src}
      alt={alt}
      onError={(event) => {
        setFallback(true);
        onError?.(event);
      }}
    />
  );
}
