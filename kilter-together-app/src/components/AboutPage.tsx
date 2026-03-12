import { Star } from "lucide-react";
import { Link } from "react-router-dom";
import BrandWordmark from "@/components/BrandWordmark";
import { HeaderNavLink } from "@/components/HeaderNavAction";
import MobilePageHeader from "@/components/MobilePageHeader";

export default function AboutPage() {
  return (
    <div className="min-h-screen bg-[#faf7f1]">
      <div className="mx-auto flex min-h-screen max-w-6xl flex-col bg-[#faf7f1] px-4 pb-10 pt-4 sm:px-6 sm:pb-24 sm:pt-6">
        <MobilePageHeader title="About Kilter Together" backTo="/" backLabel="Community mode" />
        <header className="hidden flex-wrap items-start justify-between gap-4 py-2 md:flex">
          <h1 className="leading-none">
            <Link to="/" aria-label="Back to home page" className="inline-flex">
              <BrandWordmark />
            </Link>
          </h1>
          <div className="flex flex-wrap items-center gap-2">
            <HeaderNavLink to="/settings">Settings</HeaderNavLink>
            <HeaderNavLink to="/">Community mode</HeaderNavLink>
            <HeaderNavLink to="/solo">Solo browse</HeaderNavLink>
          </div>
        </header>

        <main className="mx-auto flex w-full max-w-5xl flex-1 items-center bg-[#faf7f1] py-4 sm:py-8">
          <section className="grid w-full gap-6 sm:gap-8 lg:grid-cols-[1.05fr_0.95fr] lg:items-center">
            <div className="space-y-6 font-serif text-pretty text-[1.28rem] leading-9 text-neutral-900 sm:text-[1.48rem] sm:leading-10">
              <h2 className="text-4xl font-semibold leading-tight text-neutral-950 sm:text-5xl">
                Hi, I&apos;m{" "}
                <a
                  href="https://gabrielongzm.com"
                  target="_blank"
                  rel="noreferrer"
                  className="highlight-link font-semibold transition-colors hover:text-neutral-700"
                >
                  Gabriel
                </a>
                .
              </h2>

              <p>
                I built <strong>Kilter Together</strong> because I wanted board
                sessions to feel more collaborative than a single person scrolling
                through their climbs
                while everyone else is too shy to ask if they can alternate sets.
              </p>

              <p>I like software that gets out of the way.</p>

              <p>
                The goal of <strong>Kilter Together</strong> is simple. A host
                connects one account, shares a room, then the whole group can vote,
                queue climbs, and session together.
              </p>

              <p>
                If you like this project, I&apos;d appreciate a{" "}
                <a
                  href="https://github.com/gongahkia/kilter-together"
                  target="_blank"
                  rel="noreferrer"
                  className="highlight-link transition-colors hover:text-neutral-700"
                >
                  <Star className="h-5 w-5 fill-current" />
                  here
                </a>
                .
              </p>

              <p>See you at the gym! :)</p>
            </div>

            <div
              aria-label="Placeholder for a future photo of Gabriel climbing with friends"
              className="relative min-h-[18rem] overflow-hidden rounded-[2rem] border border-white/70 bg-[#faf7f1] shadow-xl shadow-stone-950/5 sm:min-h-[22rem]"
            >
              <div className="absolute inset-0 bg-[radial-gradient(circle_at_22%_18%,_rgba(20,184,166,0.16),_transparent_30%),radial-gradient(circle_at_80%_28%,_rgba(14,165,233,0.12),_transparent_34%),linear-gradient(180deg,_rgba(250,247,241,1),_rgba(250,247,241,1))]" />
              <div className="absolute inset-x-[8%] top-[10%] h-[22%] rounded-[1.75rem] border border-white/70 bg-white/65" />
              <div className="absolute left-[10%] top-[38%] h-[44%] w-[38%] rounded-[2rem] border border-white/70 bg-white/75 shadow-lg shadow-stone-950/5" />
              <div className="absolute right-[10%] top-[28%] h-[54%] w-[44%] rounded-[2rem] border border-white/70 bg-white/70 shadow-lg shadow-stone-950/5" />
              <div className="absolute left-[18%] top-[26%] h-20 w-20 rounded-full bg-teal-200/75 blur-[2px]" />
              <div className="absolute left-[21%] top-[39%] h-36 w-16 rounded-full bg-slate-800/12" />
              <div className="absolute left-[16%] top-[54%] h-28 w-20 rotate-[18deg] rounded-[999px] bg-amber-200/55" />
              <div className="absolute right-[22%] top-[24%] h-24 w-24 rounded-full bg-sky-200/75 blur-[2px]" />
              <div className="absolute right-[26%] top-[39%] h-40 w-16 rounded-full bg-slate-800/12" />
              <div className="absolute right-[17%] top-[58%] h-24 w-24 -rotate-[15deg] rounded-[999px] bg-rose-200/50" />
              <div className="absolute inset-x-[12%] bottom-[8%] h-[10%] rounded-[999px] bg-slate-900/8 blur-xl" />
            </div>
          </section>
        </main>
      </div>
    </div>
  );
}
