import * as React from 'react';

interface AppCardProps {
  name: string;
  description?: string | null;
  url?: string | null;
  role?: string | null;
}

export function AppCard({ name, description, url, role }: AppCardProps) {
  return (
    <div className="flex h-full flex-col border-4 border-black bg-white shadow-brutal transition-all hover:-translate-x-0.5 hover:-translate-y-0.5 hover:shadow-brutal-lg">
      <div className="flex min-h-0 flex-1 flex-col border-b-4 border-black p-4">
        <div className="flex items-start justify-between gap-2">
          <h3 className="font-bold uppercase tracking-wider">{name}</h3>
          {role && (
            <span className="border-2 border-black px-2 py-0.5 text-xs font-bold uppercase shrink-0">
              Role: {role}
            </span>
          )}
        </div>
        {description && (
          <p className="mt-2 line-clamp-3 text-sm text-gray-600">{description}</p>
        )}
      </div>
      <div className="mt-auto p-4">
        {url ? (
          <a
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            className="block w-full border-4 border-black bg-black text-white px-4 py-2 font-bold uppercase tracking-wider text-center text-sm hover:bg-white hover:text-black transition-colors"
          >
            Open →
          </a>
        ) : (
          <span className="block w-full border-4 border-dashed border-gray-400 text-gray-400 px-4 py-2 font-bold uppercase tracking-wider text-center text-sm cursor-not-allowed">
            No URL
          </span>
        )}
      </div>
    </div>
  );
}
