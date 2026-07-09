import { useEffect, useState } from "react";
import Head from "next/head";
import Link from "next/link";
import { useRouter } from "next/router";

const NAV_ITEMS = [
  { href: "/", label: "المساعد" },
  { href: "/graph", label: "شبكة المعرفة" },
  { href: "/library", label: "المكتبة القانونية" },
  { href: "/status", label: "حالة النظام" },
  { href: "/about", label: "حول المشروع" },
];

export default function Layout({ children }) {
  const router = useRouter();
  const [theme, setTheme] = useState("light");

  useEffect(() => {
    setTheme(document.documentElement.getAttribute("data-theme") || "light");
  }, []);

  function toggleTheme() {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    document.documentElement.setAttribute("data-theme", next);
    try {
      localStorage.setItem("lawz-theme", next);
    } catch (e) {
      /* storage unavailable */
    }
  }

  return (
    <div className="app">
      <Head>
        <title>Lawz AI JO — مساعد قانون العمل الأردني</title>
      </Head>
      <div className="flagStripe" />
      <header className="header">
        <div className="headerInner">
          <Link href="/" className="brand">
            <span className="brandMark">⚖</span>
            <span>
              <span className="brandName">Lawz AI JO</span>
              <span className="brandTag">مساعد قانون العمل الأردني</span>
            </span>
          </Link>
          <nav className="nav" aria-label="التنقل الرئيسي">
            {NAV_ITEMS.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={`navLink${router.pathname === item.href ? " active" : ""}`}
              >
                {item.label}
              </Link>
            ))}
          </nav>
          <button
            type="button"
            className="themeBtn"
            onClick={toggleTheme}
            title={theme === "dark" ? "الوضع الفاتح" : "الوضع الداكن"}
            aria-label="تبديل السمة"
          >
            {theme === "dark" ? "☀️" : "🌙"}
          </button>
        </div>
      </header>
      <main className="main">{children}</main>
      <footer className="footer">
        <div className="footerInner">
          <span>
            Lawz AI JO — مشروع معلوماتي مفتوح المصدر لقانون العمل الأردني رقم 8 لسنة 1996 وتعديلاته.
          </span>
          <span>المحتوى شرح أولي ولا يُعد استشارة قانونية.</span>
        </div>
      </footer>
    </div>
  );
}
