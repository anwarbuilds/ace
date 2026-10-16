import Link from "next/link";

import { AuthWordmark } from "@/components/auth/AuthWordmark";
import { NavIcon } from "@/components/shell/NavIcon";

import { PublicHeader } from "./PublicHeader";
import { WineArtwork } from "./WineArtwork";

const journeys = [
  { number: "01", icon: "pulls" as const, title: "Pulls", copy: "Know what was checked, what arrived, and which roles qualify across transparent 15-minute activity windows.", href: "/login?next=%2Fapp%2Fpulls", action: "Explore discovery" },
  { number: "02", icon: "send" as const, title: "Applications", copy: "Record an application and see one accurate total across tracking, Pulls, navigation, and analytics.", href: "/login?next=%2Fapp%2Fapplications", action: "Explore tracking" },
  { number: "03", icon: "file" as const, title: "Resume Studio", copy: "Build on verified experience, inspect role alignment, and review careful tailoring suggestions.", href: "/login?next=%2Fapp%2Fresume-studio", action: "Explore Resume Studio" },
];

export function PublicHome() {
  return (
    <main className="wine-public wine-home">
      <WineArtwork />
      <PublicHeader />
      <section className="wine-home-hero">
        <div className="wine-home-copy">
          <div className="wine-kicker"><i /> A private career intelligence platform <b>•</b> Always working</div>
          <h1>Career intelligence,<br /><em>always on.</em></h1>
          <p className="wine-home-tag">Grow at your own pace.</p>
          <p className="wine-home-description">Discover the openings that matter, move from opportunity to application, and understand your progress without losing sight of what&apos;s next.</p>
          <div className="wine-home-actions">
            <Link className="wine-button primary" href="/login">Sign in to ace <NavIcon name="right" size="sm" /></Link>
            <a className="wine-button" href="#inside-ace">Preview Pulls <NavIcon name="right" size="sm" /></a>
          </div>
          <div className="wine-home-micro"><i /> An always-on engine. One private workspace. <b>•</b> Private by design</div>
        </div>
        <div className="wine-art-caption"><span>01 / 03</span><b>DISCOVER · DECIDE · APPLY</b></div>
      </section>

      <section className="wine-preview-section" id="inside-ace">
        <div className="wine-section-heading">
          <div><span className="eyebrow">Inside ace</span><h2>A clearer way to work.</h2><p>Go straight into recent Pulls. Every opportunity and application has a place.</p></div>
          <Link className="wine-button" href="/login?next=%2Fapp%2Fpulls">Open your workspace <NavIcon name="right" size="sm" /></Link>
        </div>
        <div className="wine-product-window" aria-label="Private Pulls workspace preview">
          <div className="wine-browser-bar"><span className="wine-browser-dots"><i /><i /><i /></span><b>ace / pulls</b><span><NavIcon name="lock" size="sm" /> Private workspace</span></div>
          <div className="wine-preview-inner">
            <aside className="wine-preview-sidebar"><AuthWordmark compact linked={false} /><strong><NavIcon name="pulls" /> Pulls</strong><span><NavIcon name="briefcase" /> Opportunities</span><span><NavIcon name="send" /> Applications</span><span><NavIcon name="chart" /> Analytics</span><span><NavIcon name="file" /> Resume Studio</span><small><i /> Monitoring active</small></aside>
            <div className="wine-preview-content">
              <div className="wine-preview-top"><b>Workspace / Pulls</b><span><i /> Discovery active</span></div>
              <div className="wine-preview-heading"><div><span className="eyebrow">Your daily starting point</span><h3>Pulls</h3><p>Review opportunities from the latest discovery windows.</p></div><Link className="wine-button primary small" href="/login?next=%2Fapp%2Fpulls">Explore Pulls</Link></div>
              <div className="wine-preview-stats"><div><b>Live</b><span>Discovery status</span></div><div><b>Real</b><span>Source checks</span></div><div><b>Private</b><span>Application history</span></div></div>
              <div className="wine-preview-pull"><header><i /><div><b>Recent opportunities</b><span>Real data appears after secure sign-in</span></div></header>{["Qualifying roles ranked for review", "Employer postings with match evidence", "Application status connected everywhere"].map((text, index) => <div className="wine-preview-row" key={text}><span>{index + 1}</span><div><b>{text}</b><small>Private owner workspace</small></div><strong>Ready</strong></div>)}</div>
            </div>
          </div>
        </div>
        <p className="wine-preview-caption"><b>PRIVATE WORKSPACE PREVIEW</b><span>No owner data is loaded on this public page.</span></p>
      </section>

      <section className="wine-journey">
        <header><span className="eyebrow">Built around your day</span><h2>From first sight to next step.</h2></header>
        <div className="wine-journey-grid">{journeys.map((item) => <article key={item.title}><span className="wine-journey-number">{item.number}</span><NavIcon name={item.icon} size="lg" /><h3>{item.title}</h3><p>{item.copy}</p><Link href={item.href}>{item.action} <NavIcon name="right" size="sm" /></Link></article>)}</div>
      </section>
      <footer className="wine-public-footer"><AuthWordmark compact /><span>Grow at your own pace.</span><Link className="wine-button primary small" href="/login">Sign in <NavIcon name="right" size="sm" /></Link></footer>
    </main>
  );
}
