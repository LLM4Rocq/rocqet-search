import { ImageResponse } from "next/og";

export const size = { width: 1200, height: 630 };
export const contentType = "image/png";
export const alt = "Rocqet — semantic search for Rocq/Coq libraries";

export default function OGImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          padding: "80px",
          background: "#09090b",
          fontFamily: "monospace",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 20,
            marginBottom: 36,
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              width: 84,
              height: 84,
              borderRadius: 18,
              background: "#4f46e5",
              color: "#fff",
              fontSize: 48,
              fontWeight: 700,
            }}
          >
            R
          </div>
          <div style={{ display: "flex", color: "#fafafa", fontSize: 72, fontWeight: 700 }}>
            Rocqet
          </div>
        </div>
        <div style={{ display: "flex", color: "#a1a1aa", fontSize: 34, maxWidth: 920 }}>
          Semantic search over Rocq/Coq libraries — describe a lemma in plain
          English, find it even if you don&apos;t know its name.
        </div>
        <div style={{ display: "flex", gap: 14, marginTop: 48 }}>
          {["stdlib", "MathComp", "MathComp-Analysis", "GeoCoq"].map((lib) => (
            <div
              key={lib}
              style={{
                display: "flex",
                color: "#818cf8",
                fontSize: 24,
                padding: "8px 18px",
                borderRadius: 999,
                border: "1px solid #303034",
              }}
            >
              {lib}
            </div>
          ))}
        </div>
      </div>
    ),
    { ...size }
  );
}
