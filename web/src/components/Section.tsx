import { ReactNode } from "react";

type SectionProps = {
  title: string;
  subtitle?: string;
  children: ReactNode;
};

export default function Section({ title, subtitle, children }: SectionProps) {
  return (
    <section className="section">
      <div className="section-head">
        <h2>{title}</h2>
        {subtitle ? <p className="subtitle">{subtitle}</p> : null}
      </div>
      <div className="section-content">{children}</div>
    </section>
  );
}
