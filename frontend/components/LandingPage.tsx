"use client";

import Link from "next/link";
import { useState } from "react";

function Brand({ footer = false }: { footer?: boolean }) {
  return (
    <Link className="brand" href="/" aria-label="PipeSmith về đầu trang">
      <span className="brandmark" aria-hidden="true">
        <span />
      </span>
      {footer ? (
        "pipesmith."
      ) : (
        <>
          pipe<span style={{ color: "#e58c70" }}>smith</span>
          <span className="brand-ai">AI</span>
        </>
      )}
    </Link>
  );
}

const stages = [
  ["▦", "Planner"],
  ["◇", "Duyệt kế hoạch"],
  ["⌘", "Codegen"],
  ["↗", "Testgen"],
  ["✓", "Safety + Sandbox"],
  ["◉", "Optimizer"],
];

const processSteps = [
  {
    number: "01 / YÊU CẦU",
    title: "Planner AI",
    detail: "Bạn mô tả kết quả cần có. Nếu thiếu thông tin, Planner hỏi bạn để làm rõ.",
  },
  {
    number: "02 / PHÊ DUYỆT",
    title: "Duyệt kế hoạch",
    detail: "Bạn xem và duyệt kế hoạch trước khi hệ thống bắt đầu tạo code.",
  },
  {
    number: "03 / TẠO PIPELINE",
    title: "Codegen AI",
    detail: "Tạo các thành phần pipeline từ đặc tả và cấu trúc dữ liệu.",
  },
  {
    number: "04 / KIỂM THỬ",
    title: "Testgen AI",
    detail: "Tạo kiểm thử độc lập để đối chiếu kết quả với yêu cầu.",
  },
  {
    number: "05 / XÁC MINH",
    title: "Safety + sandbox",
    detail: "Kiểm tra an toàn rồi chạy thử. Nếu chưa đạt, Codegen sửa và kiểm tra lại.",
  },
  {
    number: "06 / TỐI ƯU",
    title: "Optimizer AI",
    detail: "Chỉ đề xuất tối ưu khi cần; thay đổi được áp dụng sẽ được kiểm tra lại.",
  },
  {
    number: "07 / ĐÓNG GÓI",
    title: "Chuẩn bị kết quả",
    detail: "Đóng gói pipeline và kết quả kiểm tra để bạn xem xét.",
  },
  {
    number: "08 / PHÊ DUYỆT",
    title: "Bạn quyết định",
    detail: "Bạn duyệt kết quả cuối cùng để hoàn tất.",
  },
];

export function LandingPage() {
  const [menuOpen, setMenuOpen] = useState(false);
  const closeMenu = () => setMenuOpen(false);

  return (
    <div className="marketingRoot">
      <main className="page landing-page">
        <div className="shell">
          <header className="nav" aria-label="Điều hướng chính">
            <Brand />
            <nav id="navlinks" className={"navlinks" + (menuOpen ? " open" : "")} aria-label="Liên kết trang">
              <a href="#tinh-nang" onClick={closeMenu}>
                Tính năng
              </a>
              <a href="#quy-trinh" onClick={closeMenu}>
                Quy trình
              </a>
              <a href="#kiem-soat" onClick={closeMenu}>
                Kiểm soát
              </a>
              <a href="#ve-chung-toi" onClick={closeMenu}>
                Về dự án
              </a>
            </nav>
            <div className="nav-actions">
              <Link href="/login" className="login">
                Đăng nhập
              </Link>
              <Link href="/login" className="btn btn-dark">
                Tham gia <span className="arrow">↗</span>
              </Link>
              <button
                className="mobile-nav"
                type="button"
                aria-label={menuOpen ? "Đóng menu" : "Mở menu"}
                aria-controls="navlinks"
                aria-expanded={menuOpen}
                onClick={() => setMenuOpen((open) => !open)}
              >
                {menuOpen ? "×" : "☰"}
              </button>
            </div>
          </header>

          <section className="hero" id="dau-trang">
            <div className="hero-copy">
              <div className="eyebrow">
                <span className="eyebrow-dot" />
                AI-NATIVE DATA PIPELINE WORKSPACE
              </div>
              <h1>
                Từ yêu cầu.
                <br />
                Đến <span className="highlight">pipeline</span>
                <br />
                dữ liệu.
              </h1>
              <p className="hero-desc">
                Bạn mô tả điều mình cần. PipeSmith lập kế hoạch, tạo và kiểm tra pipeline — với bạn duyệt kế hoạch trước
                khi tạo code và duyệt kết quả trước khi hoàn tất.
              </p>
              <div className="hero-cta">
                <Link href="/login" className="btn btn-dark">
                  Tham gia PipeSmith <span className="arrow">↗</span>
                </Link>
                <a href="#quy-trinh" className="btn btn-light">
                  Khám phá cách hoạt động <span className="arrow">↓</span>
                </a>
              </div>
              <div className="hero-details">
                <span>
                  <i className="check-dot">✓</i> Yêu cầu bằng ngôn ngữ tự nhiên
                </span>
                <span>
                  <i className="check-dot">✓</i> Bạn giữ quyền phê duyệt
                </span>
              </div>
            </div>

            <div className="hero-visual" aria-label="Minh họa giao diện workspace và quy trình PipeSmith">
              <div className="glow-a" />
              <div className="glow-b" />
              <span className="spark spark-one">✳</span>
              <span className="spark spark-two">✦</span>
              <div className="app-window">
                <div className="app-top">
                  <span className="traffic" />
                  <span className="traffic" />
                  <span className="traffic" />
                  <span className="top-url">PipeSmith / workspace / demo</span>
                </div>
                <div className="app-body">
                  <aside className="app-rail" aria-hidden="true">
                    <span className="rail-logo" />
                    <span className="rail-item active" />
                    <span className="rail-item" />
                    <span className="rail-item" />
                    <span className="rail-item" />
                  </aside>
                  <div className="app-main">
                    <div className="demo-row">
                      <div>
                        <div className="mini-kicker">PIPELINE WORKSPACE</div>
                        <h2 className="demo-title">Một yêu cầu. Quy trình rõ ràng.</h2>
                      </div>
                      <span className="tag">MINH HỌA</span>
                    </div>
                    <div className="demo-prompt">
                      <div className="mini-kicker">YÊU CẦU DỮ LIỆU</div>
                      <strong>“Tạo báo cáo doanh thu theo ngày từ dữ liệu đơn hàng.”</strong>
                    </div>
                    <div className="diagram-label">
                      <strong>Pipeline hiện tại</strong>
                      <span>6 giai đoạn chính</span>
                    </div>
                    <div className="steps">
                      {stages.map(([icon, label]) => (
                        <div className="step" key={label}>
                          <div className="step-icon">{icon}</div>
                          <div className="step-text">{label}</div>
                        </div>
                      ))}
                    </div>
                    <div className="status-row">
                      <span className="status-icon">!</span>
                      Hai bước phê duyệt do bạn quyết định
                    </div>
                  </div>
                </div>
              </div>
              <div className="float-note">
                <span className="dot">✓</span>
                <span>
                  <b>AI + Human oversight</b>
                  <small>Duyệt kế hoạch và kết quả cuối</small>
                </span>
              </div>
              <div className="visual-caption">* Giao diện minh họa, không phải kết quả chạy thực tế.</div>
            </div>
          </section>

          <div className="trust-band">
            <div className="label">Thiết kế cho quy trình dữ liệu có kiểm soát</div>
            <div className="trust-points">
              <span>01 / Schema context</span>
              <span>02 / AI workflow</span>
              <span>03 / Kiểm tra sandbox</span>
              <span>04 / Human review</span>
            </div>
          </div>
        </div>

        <section className="section" id="tinh-nang">
          <div className="shell">
            <div className="section-head">
              <div>
                <div className="number">01 / VÌ SAO PIPESMITH?</div>
                <h2>
                  Ít thao tác lặp lại.
                  <br />
                  Nhiều thời gian cho dữ liệu.
                </h2>
              </div>
              <p className="section-intro">
                Từ yêu cầu ban đầu đến pipeline được kiểm tra, từng bước đều diễn ra trong cùng một workspace.
              </p>
            </div>
            <div className="features">
              <article className="feature one">
                <div className="feature-counter">FEATURE / 01</div>
                <div className="corner">↗</div>
                <div className="icon-shell">
                  <svg viewBox="0 0 32 32" aria-hidden="true">
                    <rect x="4" y="5" width="24" height="22" rx="5" />
                    <path d="M9 12h14M9 17h9M9 22h12" />
                  </svg>
                </div>
                <h3>Hiểu yêu cầu</h3>
                <p>Planner dùng yêu cầu và ngữ cảnh schema để lập đặc tả; khi cần, sẽ hỏi bạn làm rõ.</p>
              </article>
              <article className="feature two">
                <div className="feature-counter">FEATURE / 02</div>
                <div className="corner">✳</div>
                <div className="icon-shell">
                  <svg viewBox="0 0 32 32" aria-hidden="true">
                    <rect x="3" y="6" width="26" height="20" rx="4" />
                    <path d="m11 12-4 4 4 4m10-8 4 4-4 4m-7 2 4-12" />
                  </svg>
                </div>
                <h3>Tạo & tối ưu SQL</h3>
                <p>Codegen và Testgen tạo pipeline cùng kiểm thử; Optimizer đề xuất cải thiện khi có ích.</p>
              </article>
              <article className="feature three">
                <div className="feature-counter">FEATURE / 03</div>
                <div className="corner">◎</div>
                <div className="icon-shell">
                  <svg viewBox="0 0 32 32" aria-hidden="true">
                    <path d="M16 3 27 8v8c0 7-4.4 10.5-11 13C9.4 26.5 5 23 5 16V8z" />
                    <path d="m11 16 3.4 3.3L21.5 12" />
                  </svg>
                </div>
                <h3>Kiểm tra & phê duyệt</h3>
                <p>Pipeline qua kiểm tra an toàn và sandbox; bạn duyệt kế hoạch lẫn kết quả cuối.</p>
              </article>
            </div>
          </div>
        </section>

        <section className="section process" id="quy-trinh">
          <div className="shell">
            <div className="process-top">
              <div className="number">02 / CÁCH HOẠT ĐỘNG</div>
              <h2>
                Một quy trình.
                <br />
                Rõ ràng ở từng bước.
              </h2>
            </div>
            <div className="process-steps">
              {processSteps.map((step) => (
                <article className="process-step" key={step.number}>
                  <div className="process-step-index">{step.number}</div>
                  <h3>{step.title}</h3>
                  <p>{step.detail}</p>
                </article>
              ))}
            </div>
            <div className="process-notes">
              <p>
                <strong>Cần làm rõ?</strong> Planner hỏi bạn trước khi tiếp tục.
              </p>
              <p>
                <strong>Kiểm tra chưa đạt?</strong> Codegen sửa, rồi Safety và Sandbox chạy lại.
              </p>
            </div>
          </div>
        </section>

        <section className="review" id="kiem-soat">
          <div className="shell">
            <div className="review-box">
              <div>
                <div className="eyebrow">
                  <span className="eyebrow-dot" />
                  HUMAN-IN-THE-LOOP
                </div>
                <h2>
                  AI hỗ trợ xử lý.
                  <br />
                  Bạn giữ quyền kiểm soát.
                </h2>
                <p>
                  Bạn duyệt kế hoạch trước khi sinh code, rồi xem xét pipeline đã đóng gói trước khi chấp nhận kết quả.
                </p>
              </div>
              <div className="approval-card">
                <div className="approval-header">
                  <span>Review pipeline</span>
                  <span className="pill">CẦN XEM XÉT</span>
                </div>
                <p className="approval-sub">Hai điểm kiểm soát do người dùng quyết định.</p>
                <div className="approval-data">
                  <div>
                    <strong>01 · Kế hoạch</strong>
                    <span>Duyệt trước khi tạo code</span>
                  </div>
                  <div>
                    <strong>02 · Kết quả</strong>
                    <span>Duyệt trước khi hoàn tất</span>
                  </div>
                </div>
                <div className="approve-row">
                  <span>Xem chi tiết</span>
                  <span>Phê duyệt ↗</span>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="cta" id="ve-chung-toi">
          <div className="shell">
            <div className="cta-inner">
              <div className="number">PIPE SMITH / START YOUR WORKFLOW</div>
              <h2>
                Biến ý tưởng dữ liệu
                <br />
                thành quy trình thực tế.
              </h2>
              <p>Khám phá quy trình dữ liệu có AI hỗ trợ và con người phê duyệt.</p>
              <Link href="/login" className="btn btn-dark">
                Tham gia PipeSmith <span className="arrow">↗</span>
              </Link>
            </div>
          </div>
        </section>

        <footer className="shell landing-footer">
          <Brand footer />
          <div>AI-powered data pipeline workspace · P-113</div>
          <aside>
            <a href="#tinh-nang">Tính năng</a>
            <a href="#quy-trinh">Quy trình</a>
            <Link href="/login">Đăng nhập</Link>
          </aside>
        </footer>
      </main>
    </div>
  );
}
