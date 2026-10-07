import { ChevronRight, Home } from 'lucide-react';
import { Link } from 'react-router-dom';

export default function Breadcrumbs({ items = [], ariaLabel = 'Breadcrumb', className = '' }) {
    const visibleItems = Array.isArray(items) ? items.filter(Boolean) : [];
    if (!visibleItems.length) return null;

    return (
        <nav aria-label={ariaLabel} className={className}>
            <ol className="flex flex-wrap items-center gap-1.5 text-xs text-slate-500 dark:text-zinc-400">
                {visibleItems.map((item, index) => {
                    const isLast = index === visibleItems.length - 1;
                    const label = item.label || '';
                    const content = (
                        <span className={`inline-flex items-center gap-1.5 ${isLast ? 'font-semibold text-slate-700 dark:text-zinc-200' : 'hover:text-slate-700 dark:hover:text-zinc-200'}`}>
                            {index === 0 ? <Home size={12} className="shrink-0" /> : null}
                            <span className="truncate">{label}</span>
                        </span>
                    );

                    return (
                        <li key={`${label}-${index}`} className="inline-flex items-center gap-1.5 min-w-0">
                            {index > 0 ? <ChevronRight size={12} className="shrink-0 text-slate-400 dark:text-zinc-500" /> : null}
                            {item.href && !isLast ? (
                                <Link to={item.href} className="min-w-0">
                                    {content}
                                </Link>
                            ) : (
                                <span className="min-w-0">{content}</span>
                            )}
                        </li>
                    );
                })}
            </ol>
        </nav>
    );
}

export { Breadcrumbs };


