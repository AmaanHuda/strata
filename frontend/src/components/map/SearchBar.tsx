import { css } from "@emotion/react";
import { useMemo, useState } from "react";
import { MapPin, Search } from "lucide-react";

type SearchResult = {
  lat: string;
  lon: string;
  display_name: string;
};

export function SearchBar({
  onLocationSelect,
}: {
  onLocationSelect: (lat: number, lng: number) => void;
}) {
  const [query, setQuery] = useState("");
  const [isSearching, setIsSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const placeholder = useMemo(
    () => "Search city, place, or address",
    []
  );

  const handleSearch = async () => {
    const trimmed = query.trim();
    if (!trimmed) return;

    setIsSearching(true);
    setError(null);

    try {
      const url = new URL("https://nominatim.openstreetmap.org/search");
      url.searchParams.set("format", "jsonv2");
      url.searchParams.set("limit", "1");
      url.searchParams.set("q", trimmed);

      const response = await fetch(url.toString(), {
        headers: {
          "Accept-Language": "en",
        },
      });
      const results = (await response.json()) as SearchResult[];

      if (!results.length) {
        setError("No location found");
        return;
      }

      onLocationSelect(Number(results[0].lat), Number(results[0].lon));
    } catch (searchError) {
      console.error(searchError);
      setError("Search failed");
    } finally {
      setIsSearching(false);
    }
  };

  return (
    <div
      css={css({
        position: "relative",
        zIndex: 2,
        width: "100%",
        maxWidth: "760px",
        alignSelf: "stretch",
        margin: "0 auto",
        display: "flex",
        flexDirection: "column",
        gap: "0.4rem",
      })}
    >
      <div
        css={css({
          display: "flex",
          flexWrap: "wrap",
          gap: "0.5rem",
          alignItems: "center",
          padding: "0.5rem 0.5rem 0.5rem 0.9rem",
          background: "#FFFFFF",
          borderRadius: "14px",
          boxShadow: "4px 4px 0px #0F172A",
          border: "2.5px solid #0F172A",
          ":focus-within": {
            boxShadow: "4px 4px 0px #2563EB",
            borderColor: "#2563EB",
          },
        })}
      >
        <div
          css={css({
            width: "2.25rem",
            height: "2.25rem",
            borderRadius: "10px",
            display: "grid",
            placeItems: "center",
            background: "#EFF6FF",
            border: `1.5px solid #0F172A`,
            color: "#2563EB",
            flexShrink: 0,
          })}
        >
          <MapPin size={14} strokeWidth={2.5} />
        </div>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              void handleSearch();
            }
          }}
          placeholder={placeholder}
          css={css({
            flex: 1,
            minWidth: "14rem",
            border: "none",
            outline: "none",
            background: "transparent",
            fontSize: "14px",
            fontWeight: 600,
            color: "#0F172A",
            padding: "0.2rem 0",
            "::placeholder": { color: "#737686", fontWeight: 500 },
          })}
        />
        <button
          type="button"
          onClick={() => void handleSearch()}
          disabled={isSearching}
          css={css({
            display: "inline-flex",
            alignItems: "center",
            gap: "0.35rem",
            flexShrink: 0,
            border: `2px solid #0F172A`,
            borderRadius: "10px",
            padding: "0.55rem 1rem",
            backgroundColor: "#2563EB",
            color: "#fff",
            cursor: isSearching ? "wait" : "pointer",
            fontSize: "13px",
            fontWeight: 800,
            opacity: isSearching ? 0.85 : 1,
            boxShadow: "2px 2px 0px #0F172A",
            transition: "transform 0.16s ease, box-shadow 0.16s ease",
            ":hover": {
              transform: "translate(-1px, -1px)",
              boxShadow: "3px 3px 0px #0F172A",
            },
            ":active": {
              transform: "translate(1px, 1px)",
              boxShadow: "0px 0px 0px #0F172A",
            },
          })}
        >
          <Search size={14} strokeWidth={2.5} />
          {isSearching ? "Searching" : "Search"}
        </button>
      </div>

      {error && (
        <div
          css={css({
            marginLeft: "0.25rem",
            color: "#93000A",
            fontSize: "12px",
            fontWeight: 700,
            backgroundColor: "#FFDAD6",
            border: "1.5px solid #0F172A",
            boxShadow: "2px 2px 0px #0F172A",
            padding: "0.35rem 0.7rem",
            borderRadius: "10px",
            width: "fit-content",
          })}
        >
          {error}
        </div>
      )}
    </div>
  );
}
