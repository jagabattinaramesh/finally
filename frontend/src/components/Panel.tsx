import { ReactNode } from "react";

type Props = {
  title: string;
  badge?: ReactNode;
  right?: ReactNode;
  className?: string;
  bodyClassName?: string;
  children: ReactNode;
  corners?: boolean;
};

export function Panel({ title, badge, right, className = "", bodyClassName = "", children, corners }: Props) {
  return (
    <section className={`panel ${corners ? "corners" : ""} ${className}`}>
      {corners ? (
        <>
          <span className="c1" />
          <span className="c2" />
        </>
      ) : null}
      <header className="flex items-center justify-between px-3 py-1.5 border-b border-line">
        <div className="flex items-center gap-2">
          <span className="panel-title">{title}</span>
          {badge}
        </div>
        {right}
      </header>
      <div className={bodyClassName}>{children}</div>
    </section>
  );
}
