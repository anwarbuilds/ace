"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState, useTransition } from "react";

import { Icon } from "@/components/Icon";
import { CompanyIdentity } from "@/components/CompanyIdentity";
import { Popover, usePopover } from "@/components/shell/Popover";
import { getJson } from "@/lib/client";
import { TIER_LABEL } from "@/lib/format";
import {
  CLEARED,
  DEFAULT_SORTS,
  SORTS,
  TIERS,
  facetParams,
  listHref,
  sortSentence,
  toggledSort,
  type ListState,
} from "@/lib/listState";
import type { Facet, Facets } from "@/lib/types";

const ORDINAL = ["1st", "2nd", "3rd"];
const FILTER_PREVIEW = 8;

export function useListNav(state: ListState) {
  const router = useRouter();
  const base = usePathname();
  const [pending, start] = useTransition();
  const go = (change: Partial<ListState>, replace = false) => {
    const href = listHref(base, state, change);
    start(() => (replace ? router.replace(href, { scroll: false }) : router.push(href, { scroll: false })));
  };
  return { go, pending, base };
}


function FilterMenu({ state, onPick }: { state: ListState; onPick: (change: Partial<ListState>) => void }) {
  const [facets, setFacets] = useState<Facets | null>(null);
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    getJson<Facets>("/api/facets", facetParams(state))
      .then(setFacets)
      .catch(() => setFacets({ companies: [], sources: [], families: [], priorities: [], statuses: [], sorts: [] }));
    input.current?.focus();
  }, [state]);

  const q = query.trim().toLowerCase();
  const hit = (o: Facet) => !q || o.value.toLowerCase().includes(q);
  // Searching or expanding a group shows all of it; the list scrolls.
  const cut = (key: string, list: Facet[]) => (q || open[key] ? list : list.slice(0, FILTER_PREVIEW));
  const more = (key: string, list: Facet[]) =>
    !q && !open[key] && list.length > FILTER_PREVIEW ? (
      <button className="pop-more" onClick={() => setOpen((o) => ({ ...o, [key]: true }))}>
        Show {list.length - FILTER_PREVIEW} more
      </button>
    ) : null;

  const group = (title: string, raw: Facet[] | undefined, key: "companies" | "sources" | "families", fold: boolean) => {
    const list = (raw ?? []).filter(hit);
    if (!list.length) return null;
    return (
      <>
        <div className="pop-group">{title}</div>
        {cut(key, list).map((o) => (
          <button
            key={o.value}
            className={`pop-opt${state[key].includes(o.value) ? " on" : ""}`}
            onClick={() => onPick({ [key]: state[key].includes(o.value) ? state[key] : [...state[key], o.value] })}
          >
            {key === "companies" ? <CompanyIdentity name={o.value} /> : fold ? o.value.replace(/_/g, " ").toLowerCase() : o.value}
            <span className="n">{o.count}</span>
          </button>
        ))}
        {more(key, list)}
      </>
    );
  };

  const exclude = (facets?.companies ?? []).filter(hit);

  return (
    <>
      <h4>Add a filter</h4>
      <input
        ref={input}
        className="pop-search"
        id="filter-q"
        placeholder="Search companies and sources"
        autoComplete="off"
        aria-label="Search filters"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      <div className="pop-list">
        {!facets ? (
          <div className="pop-note">Loading</div>
        ) : (
          <>
            {!q ? (
              <>
                <div className="pop-group">Quick</div>
                <button className={`pop-opt${state.verified ? " on" : ""}`} onClick={() => onPick({ verified: true })}>
                  Description available
                </button>
              </>
            ) : null}
            {group("Only this company", facets.companies, "companies", false)}
            {exclude.length ? (
              <>
                <div className="pop-group">Hide a company</div>
                {cut("exclude", exclude).map((o) => {
                  const off = state.excluded.includes(o.value);
                  return (
                    <button
                      key={o.value}
                      className={`pop-opt${off ? " on" : ""}`}
                      onClick={() =>
                        onPick({
                          excluded: off ? state.excluded.filter((x) => x !== o.value) : [...state.excluded, o.value],
                        })
                      }
                    >
                      <Icon name="minus" size={13} />
                      <CompanyIdentity name={o.value} />
                      <span className="n">{o.count}</span>
                    </button>
                  );
                })}
                {more("exclude", exclude)}
              </>
            ) : null}
            {group("Source", facets.sources, "sources", true)}
            {group("Role family", facets.families, "families", true)}
            {q && !facets.companies.some(hit) && !facets.sources.some(hit) && !facets.families.some(hit) ? (
              <div className="pop-note">Nothing matches that.</div>
            ) : null}
          </>
        )}
      </div>
    </>
  );
}

export function ListControls({ state }: { state: ListState }) {
  const { go } = useListNav(state);
  const [q, setQ] = useState(state.q);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const sortPop = usePopover();
  const filterPop = usePopover();

  // Follow the URL when it changes from elsewhere (Back, a chip, Clear).
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => setQ(state.q), [state.q]);

  const onSearch = (value: string) => {
    setQ(value);
    if (timer.current) clearTimeout(timer.current);
    // One request per word typed straight through, not one per letter.
    timer.current = setTimeout(() => go({ q: value.trim() }, true), 350);
  };

  const applied = state.page === "applied";
  const valueChips = [
    ...state.companies.map((v) => ({ label: v, company: v, drop: { companies: state.companies.filter((x) => x !== v) } })),
    ...state.sources.map((v) => ({ label: v.replace(/_/g, " ").toLowerCase(), drop: { sources: state.sources.filter((x) => x !== v) } })),
    ...state.families.map((v) => ({
      label: v.replace(/_/g, " ").toLowerCase(),
      drop: { families: state.families.filter((x) => x !== v) },
    })),
    ...(state.verified ? [{ label: "Description available", drop: { verified: false } }] : []),
    ...(state.recent ? [{ label: "Last 15 days", drop: { recent: false } }] : []),
    ...(state.includeOld ? [{ label: "Includes 30+ day old openings", drop: { includeOld: false } }] : []),
  ];
  const anyActive = valueChips.length || state.excluded.length || state.tiers.length || state.q;
  const changedSort = state.sorts.join(",") !== DEFAULT_SORTS.join(",") && !(state.view === "new" || state.view === "latest");

  return (
    <div className="controls">
      <div className="ctl-row">
        <label className="search">
          <Icon name="search" />
          <input
            id="q"
            type="search"
            placeholder="Search company, title, skill"
            aria-label="Search"
            aria-keyshortcuts="/"
            autoComplete="off"
            spellCheck={false}
            value={q}
            onChange={(e) => onSearch(e.target.value)}
          />
        </label>
        {applied ? null : (
          <div className="ctl-grp">
            <span className="ctl-label">Sort</span>
            {SORTS.slice(0, 4).map(([key, label]) => {
              const i = state.sorts.indexOf(key);
              const on = i >= 0;
              return (
                <button
                  key={key}
                  className={`chip${on ? " on" : ""}`}
                  aria-pressed={on}
                  title={on ? `Sorted by this ${ORDINAL[i]}. Click to turn it off.` : "Off. Click to sort by this first."}
                  onClick={() => go({ sorts: toggledSort(state.sorts, key) })}
                >
                  {label}
                  {on ? <span className="chip-n">{ORDINAL[i]}</span> : null}
                </button>
              );
            })}
            <button className="link-btn" onClick={(e) => sortPop.open(e.currentTarget)}>
              More
            </button>
          </div>
        )}
      </div>
      {applied || !state.sorts.length ? null : (
        <div className="ctl-row ctl-sortline">
          <span className="sort-says">Showing {sortSentence(state.sorts)}.</span>
          {changedSort ? (
            <button className="link-btn" onClick={() => go({ sorts: DEFAULT_SORTS })}>
              Reset to default
            </button>
          ) : null}
        </div>
      )}
      <div className="ctl-row">
        <div className="ctl-grp">
          <span className="ctl-label">Company tier</span>
          {TIERS.map((t) => {
            const on = state.tiers.includes(t);
            return (
              <button
                key={t}
                className={`chip${on ? (t === "BIG_TECH" ? " on-gold" : " on") : ""}`}
                aria-pressed={on}
                onClick={() => go({ tiers: on ? state.tiers.filter((x) => x !== t) : [...state.tiers, t] })}
              >
                {TIER_LABEL[t]}
              </button>
            );
          })}
        </div>
        <div className="ctl-grp">
          <span className="ctl-label">Show only</span>
          <button
            className={`chip${state.early ? " on" : ""}`}
            aria-pressed={state.early}
            onClick={() => go({ early: !state.early })}
            title="Roles labelled early career, plus any stating three years or less. Postings that state no requirement at all are hidden while this is on."
          >
            Early career
          </button>
          <button
            className={`chip${state.newGrad ? " on" : ""}`}
            aria-pressed={state.newGrad}
            onClick={() => go({ newGrad: !state.newGrad })}
            title="Only postings whose title says new grad, recent graduate, campus or university hire. Narrower than Early career, which also covers junior, associate and Engineer I."
          >
            New grad
          </button>
          <button className="chip" onClick={(e) => filterPop.open(e.currentTarget)}>
            <Icon name="plus" />
            Add filter
          </button>
        </div>
      </div>
      {anyActive ? (
        <div className="ctl-row ctl-active">
          <span className="ctl-label">Filtering by</span>
          {valueChips.map((c) => (
            <button key={c.label} className="chip on" onClick={() => go(c.drop)}>
              {"company" in c ? <CompanyIdentity name={c.company} /> : c.label}
              <span className="chip-x">&times;</span>
            </button>
          ))}
          {state.excluded.map((name) => (
            <button
              key={name}
              className="chip excluded"
              title="Excluded. Click to put it back."
              onClick={() => go({ excluded: state.excluded.filter((x) => x !== name) })}
            >
              <Icon name="minus" size={13} />
              <CompanyIdentity name={name} />
            </button>
          ))}
          {!valueChips.length && !state.excluded.length ? (
            <span className="ctl-none">
              {state.tiers.map((t) => TIER_LABEL[t]).join(", ")}
              {state.q ? `${state.tiers.length ? ", " : ""}search "${state.q}"` : ""}
            </span>
          ) : null}
          <button className="link-btn" onClick={() => go({ ...CLEARED, recent: false, includeOld: false })}>
            Clear all
          </button>
        </div>
      ) : null}

      <Popover anchor={sortPop.anchor} onClose={sortPop.close}>
        <h4>Sort by</h4>
        <p>Sorts combine. The number shows the order they apply in.</p>
        <div className="pop-list">
          {SORTS.map(([key, label]) => {
            const i = state.sorts.indexOf(key);
            return (
              <button
                key={key}
                className={`pop-opt${i >= 0 ? " on" : ""}`}
                onClick={() => {
                  sortPop.close();
                  go({ sorts: toggledSort(state.sorts, key) });
                }}
              >
                {label}
                {i >= 0 ? <span className="n">{i + 1}</span> : null}
              </button>
            );
          })}
        </div>
      </Popover>
      <Popover anchor={filterPop.anchor} onClose={filterPop.close}>
        <FilterMenu
          state={state}
          onPick={(change) => {
            filterPop.close();
            go(change);
          }}
        />
      </Popover>
    </div>
  );
}
