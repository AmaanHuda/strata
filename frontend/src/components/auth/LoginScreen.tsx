import { css } from "@emotion/react";
import { useState } from "react";
import { Layers3, Lock, User, AlertCircle } from "lucide-react";
import { useAuthStore } from "@/state/authStore";
import { INK } from "@/theme/color";

export function LoginScreen() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const { login, isLoading, error } = useAuthStore();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password.trim()) return;
    await login(username.trim(), password.trim());
  };

  return (
    <div
      css={css({
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "linear-gradient(135deg, #EFF6FF 0%, #F8FAFC 60%, #E0E7FF 100%)",
        padding: "1rem",
      })}
    >
      <div
        css={css({
          background: "#FFFFFF",
          border: `3px solid ${INK}`,
          boxShadow: "8px 8px 0px #0F172A",
          borderRadius: "20px",
          padding: "2.5rem",
          width: "100%",
          maxWidth: "400px",
          display: "flex",
          flexDirection: "column",
          gap: "2rem",
        })}
      >
        {/* Logo */}
        <div css={css({ display: "flex", alignItems: "center", gap: "0.75rem" })}>
          <div
            css={css({
              width: "3rem",
              height: "3rem",
              borderRadius: "14px",
              display: "grid",
              placeItems: "center",
              background: "#2563EB",
              border: `2.5px solid ${INK}`,
              boxShadow: "2px 2px 0px #0F172A",
              color: "#fff",
              flexShrink: 0,
            })}
          >
            <Layers3 size={22} strokeWidth={2.5} />
          </div>
          <div>
            <div
              css={css({
                fontSize: "1.5rem",
                fontWeight: 800,
                color: "#0F172A",
                letterSpacing: "-0.02em",
                lineHeight: 1,
              })}
            >
              STRATA
            </div>
            <div css={css({ fontSize: "0.75rem", color: "#64748B", fontWeight: 600 })}>
              3D Cadastral Mapping System
            </div>
          </div>
        </div>

        <div>
          <h1
            css={css({
              margin: 0,
              fontSize: "1.25rem",
              fontWeight: 800,
              color: "#0F172A",
              marginBottom: "0.35rem",
            })}
          >
            Sign in to continue
          </h1>
          <p css={css({ margin: 0, fontSize: "0.8rem", color: "#64748B", fontWeight: 600 })}>
            Use your STRATA backend credentials
          </p>
        </div>

        <form
          onSubmit={(e) => void handleSubmit(e)}
          css={css({ display: "flex", flexDirection: "column", gap: "1rem" })}
        >
          {/* Username */}
          <div css={css({ display: "flex", flexDirection: "column", gap: "0.4rem" })}>
            <label
              css={css({
                fontSize: "0.7rem",
                fontWeight: 800,
                color: "#64748B",
                textTransform: "uppercase",
                letterSpacing: "0.05em",
              })}
            >
              Username
            </label>
            <div
              css={css({
                display: "flex",
                alignItems: "center",
                gap: "0.5rem",
                border: `2px solid ${INK}`,
                borderRadius: "10px",
                padding: "0.6rem 0.85rem",
                background: "#F8FAFC",
                boxShadow: "2px 2px 0px #0F172A",
                ":focus-within": {
                  borderColor: "#2563EB",
                  boxShadow: "2px 2px 0px #2563EB",
                },
              })}
            >
              <User size={16} color="#94A3B8" strokeWidth={2.5} />
              <input
                id="strata-username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Enter username"
                autoComplete="username"
                css={css({
                  flex: 1,
                  border: "none",
                  outline: "none",
                  background: "transparent",
                  fontSize: "14px",
                  fontWeight: 600,
                  color: "#0F172A",
                  "::placeholder": { color: "#94A3B8" },
                })}
              />
            </div>
          </div>

          {/* Password */}
          <div css={css({ display: "flex", flexDirection: "column", gap: "0.4rem" })}>
            <label
              css={css({
                fontSize: "0.7rem",
                fontWeight: 800,
                color: "#64748B",
                textTransform: "uppercase",
                letterSpacing: "0.05em",
              })}
            >
              Password
            </label>
            <div
              css={css({
                display: "flex",
                alignItems: "center",
                gap: "0.5rem",
                border: `2px solid ${INK}`,
                borderRadius: "10px",
                padding: "0.6rem 0.85rem",
                background: "#F8FAFC",
                boxShadow: "2px 2px 0px #0F172A",
                ":focus-within": {
                  borderColor: "#2563EB",
                  boxShadow: "2px 2px 0px #2563EB",
                },
              })}
            >
              <Lock size={16} color="#94A3B8" strokeWidth={2.5} />
              <input
                id="strata-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter password"
                autoComplete="current-password"
                css={css({
                  flex: 1,
                  border: "none",
                  outline: "none",
                  background: "transparent",
                  fontSize: "14px",
                  fontWeight: 600,
                  color: "#0F172A",
                  "::placeholder": { color: "#94A3B8" },
                })}
              />
            </div>
          </div>

          {/* Error */}
          {error && (
            <div
              css={css({
                display: "flex",
                alignItems: "center",
                gap: "0.5rem",
                padding: "0.6rem 0.85rem",
                background: "#FEF2F2",
                border: `1.5px solid #FCA5A5`,
                borderRadius: "10px",
                fontSize: "12px",
                fontWeight: 700,
                color: "#DC2626",
              })}
            >
              <AlertCircle size={14} strokeWidth={2.5} />
              {error}
            </div>
          )}

          <button
            id="strata-login-submit"
            type="submit"
            disabled={isLoading || !username || !password}
            css={css({
              width: "100%",
              padding: "0.85rem",
              background: "#2563EB",
              color: "#fff",
              border: `2.5px solid ${INK}`,
              boxShadow: "3px 3px 0px #0F172A",
              borderRadius: "12px",
              fontSize: "14px",
              fontWeight: 800,
              cursor: isLoading || !username || !password ? "not-allowed" : "pointer",
              opacity: isLoading || !username || !password ? 0.6 : 1,
              transition: "transform 0.16s ease, box-shadow 0.16s ease",
              ":hover:not(:disabled)": {
                transform: "translate(-1px, -1px)",
                boxShadow: "4px 4px 0px #0F172A",
              },
              ":active:not(:disabled)": {
                transform: "translate(2px, 2px)",
                boxShadow: "1px 1px 0px #0F172A",
              },
            })}
          >
            {isLoading ? "Signing in…" : "Sign in"}
          </button>
        </form>

        <p
          css={css({
            margin: 0,
            fontSize: "0.7rem",
            color: "#94A3B8",
            fontWeight: 600,
            textAlign: "center",
            lineHeight: 1.5,
          })}
        >
          Access requires a registered STRATA account.
          <br />
          Contact your administrator if you need access.
        </p>
      </div>
    </div>
  );
}
