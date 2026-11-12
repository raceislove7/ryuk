"use client";
import { useId } from "react";
import { label } from "../lib/api";
import type { Intent } from "../lib/contracts";
import { highlightedSourceParts } from "../lib/intent-sources";

export default function IntentSources({ intent }: { intent: Intent }) {
  const originalId = `intent-original-${useId()}`;
  const sources = intent.requirement_sources || [];
  return <section className="intent-sources" aria-label="Original request and requirement sources">
    <div>
      <p className="micro">ORIGINAL INSTRUCTION</p>
      <p id={originalId} className="original-instruction" tabIndex={-1}>
        {highlightedSourceParts(intent.query, sources).map((part, index) => part.highlighted
          ? <mark key={index}>{part.text}</mark> : <span key={index}>{part.text}</span>)}
      </p>
      <p className="subtle">Highlights show retained source quotes, not proof that every requirement was captured.</p>
    </div>
    <div>
      <p className="micro">PARSED REQUIREMENTS — CHECK FOR OMISSIONS OR CHANGED MEANING</p>
      {(["required", "preferred"] as const).map((role) => <div key={role}>
        <p className="micro">{role === "required" ? "MANDATORY" : "PREFERRED"}</p>
        {Object.keys(intent[`${role}_attributes`]).length === 0 && <p>None specified.</p>}
        <ul>{Object.entries(intent[`${role}_attributes`]).map(([name, value]) => {
          const source = sources.find((item) => item.role === role && item.name === name);
          return <li key={name}>
            <strong>{label(name)}: {String(value)}</strong>
            {source ? <blockquote aria-label={`Source quote for ${role} ${label(name)}`}>
              <a href={`#${originalId}`} aria-label={`Compare source quote for ${label(name)} with original instruction`}>
                <mark>{source.quote}</mark>
              </a>
            </blockquote> : <p className="subtle">Source quote not retained for this record.</p>}
          </li>;
        })}</ul>
      </div>)}
    </div>
  </section>;
}
