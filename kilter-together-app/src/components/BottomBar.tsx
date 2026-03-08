const heartPngSrc = "/heart.png";

export default function BottomBar() {
  return (
    <footer className="fixed inset-x-0 bottom-0 z-40 border-t border-slate-200/80 bg-white/88 px-4 py-3 shadow-[0_-12px_35px_rgba(15,23,42,0.08)] backdrop-blur">
      <div className="mx-auto flex max-w-5xl items-center justify-center text-center text-sm font-medium tracking-tight text-slate-700 sm:text-base">
        <span className="flex flex-wrap items-center justify-center gap-1.5">
          <span>Made with</span>
          {heartPngSrc ? (
            <img src={heartPngSrc} alt="love" className="h-5 w-auto object-contain" />
          ) : (
            <span className="font-semibold text-rose-600">Love</span>
          )}
          <span>for the Climbing Community by Gabriel Ong</span>
        </span>
      </div>
    </footer>
  );
}
