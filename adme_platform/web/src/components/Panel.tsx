export function Panel({
  title,
  subtitle,
  action,
  children,
  className = "",
  span = 6,
}: {
  title?: string;
  subtitle?: string;
  action?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  span?: 3 | 4 | 5 | 6 | 7 | 8 | 12;
}) {
  return (
    <section className={`panel span-${span} ${className}`}>
      {(title || action) && (
        <div className="panel-head">
          <div>
            {title && <h2>{title}</h2>}
            {subtitle && <p className="panel-sub">{subtitle}</p>}
          </div>
          {action}
        </div>
      )}
      {children}
    </section>
  );
}
