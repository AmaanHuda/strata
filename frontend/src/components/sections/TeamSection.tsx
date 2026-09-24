import { css } from "@emotion/react";
import { Circle, Github, Linkedin } from "lucide-react";
import { INK } from "@/theme/color";

const TEAM = [
  {
    initials: "AH",
    name: "Amaan Huda",
    github: "https://github.com/AmaanHuda",
    linkedin: "https://linkedin.com/in/amaan-huda",
    avatarBg: "#DBE1FF",
    avatarColor: "#00174B",
  },
  {
    initials: "DK",
    name: "Dhyana Kansara",
    github: "https://github.com/",
    linkedin: "https://linkedin.com/",
    avatarBg: "#FFDDB8",
    avatarColor: "#2A1700",
  },
  {
    initials: "RK",
    name: "Mohammed Rehan Khan",
    github: "https://github.com/",
    linkedin: "https://linkedin.com/",
    avatarBg: "#6CF8BB",
    avatarColor: "#002113",
  },
  {
    initials: "VK",
    name: "Vinayak Kesarkar",
    github: "https://github.com/",
    linkedin: "https://linkedin.com/",
    avatarBg: "#DAE2FD",
    avatarColor: "#003EA8",
  },
  {
    initials: "AM",
    name: "Arpan Maurya",
    github: "https://github.com/",
    linkedin: "https://linkedin.com/",
    avatarBg: "#DAE2FD",
    avatarColor: "#003EA8",
  },
  {
    initials: "AJ",
    name: "Ankita Jha",
    github: "https://github.com/",
    linkedin: "https://linkedin.com/",
    avatarBg: "#DAE2FD",
    avatarColor: "#003EA8",
  },
];

const DIAGNOSTICS = [
  { label: "ISRO Bhuvan Integration:", value: "CONNECTED" },
  { label: "TILE SERVER:", value: "ap-south-mumbai-01" },
  { label: "COMPRESSION:", value: "Draco v1.5.6 (8.2:1)" },
  { label: "EPSG PROJECTION:", value: "EPSG:3857 (Web Mercator)" },
];

export function TeamSection() {
  return (
    <section
      id="strata-team"
      css={css({
        width: "100%",
        borderTop: `2.5px solid ${INK}`,
        borderBottom: `2.5px solid ${INK}`,
        background: "#EAEDFF",
        padding: "3rem 1.5rem",
        display: "flex",
        flexDirection: "column",
        gap: "2rem",
      })}
    >
      <div
        css={css({
          maxWidth: "80rem",
          width: "100%",
          margin: "0 auto",
          display: "flex",
          flexDirection: "column",
          gap: "2rem",
        })}
      >
        <div
          css={css({
            display: "flex",
            flexDirection: "column",
            gap: "0.25rem",
          })}
        >
          <h3
            css={css({
              margin: 0,
              fontSize: "1.4rem",
              fontWeight: 800,
              letterSpacing: "-0.02em",
              color: "#0F172A",
            })}
          >
            Team Aeranoix
          </h3>
          <p
            css={css({
              margin: 0,
              fontSize: "14px",
              fontWeight: 500,
              color: "#434655",
            })}
          >
            Engineers & Researchers behind the STRATA 3D Reconstruction Pipeline
          </p>
        </div>

        {/* Team Cards Grid */}
        <div
          css={css({
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
            gap: "1.25rem",
          })}
        >
          {TEAM.map((member) => (
            <div
              key={member.name}
              css={css({
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: "1rem",
                padding: "1.5rem",
                background: "#FFFFFF",
                border: `2.5px solid ${INK}`,
                boxShadow: "3px 3px 0px #0F172A",
                borderRadius: "14px",
                transition: "transform 0.16s ease, box-shadow 0.16s ease",
                ":hover": {
                  transform: "translate(-2px, -2px)",
                  boxShadow: "5px 5px 0px #0F172A",
                },
              })}
            >
              <div
                css={css({
                  width: "64px",
                  height: "64px",
                  borderRadius: "50%",
                  background: member.avatarBg,
                  border: `2px solid ${INK}`,
                  boxShadow: "2px 2px 0px #0F172A",
                  display: "grid",
                  placeItems: "center",
                  fontSize: "20px",
                  fontWeight: 800,
                  color: member.avatarColor,
                  flexShrink: 0,
                })}
              >
                {member.initials}
              </div>
              <div
                css={css({
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  gap: "0.5rem",
                })}
              >
                <span
                  css={css({
                    fontSize: "16px",
                    fontWeight: 800,
                    color: "#0F172A",
                  })}
                >
                  {member.name}
                </span>

                <div
                  css={css({
                    display: "flex",
                    gap: "0.75rem",
                    marginTop: "0.25rem",
                  })}
                >
                  <a
                    href={member.github}
                    target="_blank"
                    rel="noreferrer"
                    css={css({
                      color: "#0F172A",
                      ":hover": { color: "#2563EB" },
                    })}
                  >
                    <Github size={20} />
                  </a>
                  <a
                    href={member.linkedin}
                    target="_blank"
                    rel="noreferrer"
                    css={css({
                      color: "#0F172A",
                      ":hover": { color: "#2563EB" },
                    })}
                  >
                    <Linkedin size={20} />
                  </a>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* System Diagnostics Ribbon */}
        <div
          css={css({
            display: "flex",
            flexWrap: "wrap",
            alignItems: "center",
            justifyContent: "space-between",
            gap: "1rem",
            padding: "1rem 1.25rem",
            background: "#FFFFFF",
            border: `2.5px solid ${INK}`,
            boxShadow: "2px 2px 0px #0F172A",
            borderRadius: "14px",
            fontFamily: "monospace",
            fontSize: "11px",
          })}
        >
          <div
            css={css({
              display: "flex",
              alignItems: "center",
              gap: "0.6rem",
            })}
          >
            <span
              css={css({
                position: "relative",
                display: "flex",
                width: "10px",
                height: "10px",
              })}
            >
              <span
                css={css({
                  position: "absolute",
                  inset: 0,
                  borderRadius: "999px",
                  background: "#10B981",
                  opacity: 0.75,
                })}
              />
              <span
                css={css({
                  position: "relative",
                  display: "inline-flex",
                  width: "10px",
                  height: "10px",
                  borderRadius: "999px",
                  background: "#10B981",
                  border: `1.5px solid ${INK}`,
                })}
              />
            </span>
            <span css={css({ fontWeight: 800, color: "#0F172A" })}>
              {DIAGNOSTICS[0].label}
            </span>
            <span css={css({ color: "#006C49", fontWeight: 800 })}>
              {DIAGNOSTICS[0].value}
            </span>
          </div>
          {DIAGNOSTICS.slice(1).map((d) => (
            <div key={d.label} css={css({ color: "#64748B", fontWeight: 600 })}>
              {d.label}{" "}
              <span css={css({ color: "#0F172A", fontWeight: 800 })}>
                {d.value}
              </span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
