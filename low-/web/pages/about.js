export default function AboutPage() {
  return (
    <>
      <div className="pageHead">
        <p className="eyebrow">مشروع معلوماتي مفتوح المصدر</p>
        <h1>حول Lawz AI JO</h1>
        <p className="lede">
          مساعد عربي متخصص في قانون العمل الأردني رقم 8 لسنة 1996 وتعديلاته، يجمع بين الاسترجاع
          الدلالي، والرسم المعرفي القانوني، والتوليد اللغوي — محلياً بالكامل أو عبر واجهات API خارجية
          حسب اختيارك.
        </p>
      </div>

      <div className="featureGrid">
        <div className="featureCard">
          <div className="icon">📚</div>
          <h3>مبني على النص القانوني</h3>
          <p>
            يجيب حصراً من مواد مختارة من قانون العمل الأردني ودليل شارح معتمد، ولا يخترع مواد أو
            مراجع. النصوص القانونية محفوظة كما هي دون أي تعديل.
          </p>
        </div>
        <div className="featureCard">
          <div className="icon">🕸</div>
          <h3>رسم معرفي قانوني</h3>
          <p>
            شبكة مشتقة آلياً تربط المفاهيم (الفصل التعسفي، الأجر، الإجازات…) بالمواد القانونية
            والمواضيع والمصادر، وتعزز دقة الاسترجاع وتكشف العلاقات بين الأحكام.
          </p>
        </div>
        <div className="featureCard">
          <div className="icon">🔌</div>
          <h3>مزوّدو نماذج متعددون</h3>
          <p>
            يعمل محلياً عبر Ollama دون أن تغادر بياناتك جهازك، أو عبر أي واجهة متوافقة مع OpenAI، أو
            عبر Claude API من Anthropic — مع إمكانية التبديل لكل سؤال.
          </p>
        </div>
        <div className="featureCard">
          <div className="icon">🔎</div>
          <h3>إجابات موثقة وشفافة</h3>
          <p>
            كل إجابة تعرض المراجع المعتمدة، والنصوص المسترجعة ودرجاتها، ومستوى الثقة، والمفاهيم
            القانونية التي رصدها الرسم المعرفي في سؤالك.
          </p>
        </div>
        <div className="featureCard">
          <div className="icon">📈</div>
          <h3>قابلية مراقبة كاملة</h3>
          <p>
            مقاييس Prometheus وسجلات JSON منظمة ونقاط فحص صحة وجاهزية، مع صفحة حالة حية داخل
            الواجهة.
          </p>
        </div>
        <div className="featureCard">
          <div className="icon">🛡</div>
          <h3>حدود واضحة</h3>
          <p>
            المشروع معلوماتي فقط: لا يقدم استشارات قانونية نهائية، ولا يراجع عقوداً، ولا يغني عن
            محامٍ مختص أو النص الرسمي المنشور في الجريدة الرسمية.
          </p>
        </div>
      </div>

      <div className="card" style={{ marginTop: 24 }}>
        <div className="cardTitle">🏗 كيف يعمل النظام؟</div>
        <div className="archFlow">
          <span className="archNode">سؤالك</span>
          <span className="archArrow">←</span>
          <span className="archNode">تضمين دلالي (E5)</span>
          <span className="archArrow">←</span>
          <span className="archNode">استرجاع من Weaviate</span>
          <span className="archArrow">←</span>
          <span className="archNode">تعزيز بالرسم المعرفي</span>
          <span className="archArrow">←</span>
          <span className="archNode">توليد (Ollama / OpenAI / Claude)</span>
          <span className="archArrow">←</span>
          <span className="archNode">إجابة موثقة</span>
        </div>
        <p style={{ color: "var(--text-2)", marginTop: 14, marginBottom: 0 }}>
          عند وصول سؤالك، يرصد النظام المفاهيم القانونية فيه عبر معجم مفاهيم قانون العمل، ثم يسترجع
          النصوص الأقرب دلالياً، ويرفع ترتيب النصوص التي تشارك سؤالك المفاهيم ذاتها في الرسم
          المعرفي، وأخيراً يولّد إجابة عربية ملتزمة بالنصوص المسترجعة فقط.
        </p>
      </div>

      <div className="twoCol" style={{ marginTop: 24 }}>
        <div className="card">
          <div className="cardTitle">✅ ما يقدمه المشروع</div>
          <ul className="checks">
            <li>إجابات معلوماتية عربية عن قانون العمل الأردني.</li>
            <li>مراجع واستشهادات مولدة من الخادم لكل إجابة.</li>
            <li>رسم معرفي تفاعلي للمفاهيم والمواد القانونية.</li>
            <li>مكتبة لتصفح النصوص القانونية المعتمدة.</li>
            <li>تشغيل محلي كامل أو عبر مزوّدي API خارجيين.</li>
            <li>مقاييس ومراقبة وتقييم دخاني (smoke evaluation).</li>
          </ul>
        </div>
        <div className="card">
          <div className="cardTitle">🚫 ما لا يقدمه المشروع</div>
          <ul className="checks crosses">
            <li>استشارة قانونية نهائية أو تمثيل قانوني.</li>
            <li>رفع ملفات PDF أو مراجعة عقود أو تقييم مخاطر.</li>
            <li>تعديل أو إعادة صياغة النصوص القانونية الأصلية.</li>
            <li>الإجابة عن مجالات قانونية خارج قانون العمل.</li>
          </ul>
        </div>
      </div>

      <div className="card" style={{ marginTop: 24 }}>
        <div className="cardTitle">🧰 التقنيات المستخدمة</div>
        <div className="answerMeta" style={{ margin: 0 }}>
          <span className="chip">FastAPI</span>
          <span className="chip">Weaviate</span>
          <span className="chip">Sentence-Transformers (E5)</span>
          <span className="chip">Ollama</span>
          <span className="chip">Anthropic Claude API</span>
          <span className="chip">OpenAI-compatible APIs</span>
          <span className="chip">Next.js + React</span>
          <span className="chip">Prometheus</span>
          <span className="chip">Docker Compose</span>
        </div>
      </div>

      <p className="disclaimer" style={{ marginTop: 24 }}>
        ⚠ هذا المشروع شرح أولي مبني على المصادر المسترجعة ولا يُعد استشارة قانونية ولا يغني عن مراجعة
        محامٍ مختص أو النص القانوني الرسمي.
      </p>
    </>
  );
}
