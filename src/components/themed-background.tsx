export function ThemedBackground() {
  return (
    <div className="pointer-events-none fixed inset-0 -z-10 overflow-hidden" aria-hidden>
      {/* base wash */}
      <div className="absolute inset-0 bg-background" />

      {/* soft green orb top-right */}
      <div
        className="absolute -top-40 -right-40 h-[560px] w-[560px] rounded-full opacity-30 blur-3xl"
        style={{ background: "radial-gradient(circle, var(--brand) 0%, transparent 65%)" }}
      />
      {/* gold orb bottom-left */}
      <div
        className="absolute -bottom-52 -left-40 h-[620px] w-[620px] rounded-full opacity-25 blur-3xl"
        style={{ background: "radial-gradient(circle, var(--gold) 0%, transparent 65%)" }}
      />

      {/* topographic contour lines */}
      <svg
        className="absolute inset-0 h-full w-full opacity-[0.07]"
        viewBox="0 0 1200 900"
        preserveAspectRatio="xMidYMid slice"
      >
        <defs>
          <pattern id="dots" width="28" height="28" patternUnits="userSpaceOnUse">
            <circle cx="1.2" cy="1.2" r="1.2" fill="currentColor" />
          </pattern>
        </defs>
        <g stroke="currentColor" fill="none" strokeWidth="1.2" className="text-brand">
          <path d="M0,520 Q300,440 600,520 T1200,520" />
          <path d="M0,570 Q300,490 600,570 T1200,570" />
          <path d="M0,620 Q300,540 600,620 T1200,620" />
          <path d="M0,670 Q300,590 600,670 T1200,670" />
          <path d="M0,720 Q300,640 600,720 T1200,720" />
        </g>
        <rect width="1200" height="900" fill="url(#dots)" className="text-brand" opacity="0.35" />
      </svg>

      {/* corner accents */}
      <svg className="absolute top-0 right-0 h-full w-1/2 opacity-[0.05]" viewBox="0 0 100 100" preserveAspectRatio="none">
        <path d="M100,0 Q75,50 100,100 L100,100 Z" fill="var(--brand)" />
      </svg>
      <svg className="absolute bottom-0 left-0 h-1/3 w-full opacity-[0.06]" viewBox="0 0 100 100" preserveAspectRatio="none">
        <path d="M0,100 Q50,70 100,100 Z" fill="var(--gold)" />
      </svg>
    </div>
  );
}
