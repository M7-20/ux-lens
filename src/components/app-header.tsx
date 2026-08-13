import { Link } from "@tanstack/react-router";

export function AppLogo({ size = 40 }: { size?: number }) {
  return <img src={`${import.meta.env.BASE_URL}logo.svg`} alt="" width={size} height={size} style={{ width: size, height: size }} aria-hidden />;
}

export function AppHeader() {
  return (
    <header className="sticky top-0 z-30 border-b border-hairline bg-surface">
      <div className="flex items-center justify-start px-4 py-3 md:px-6 md:py-4">
        <Link to="/" className="flex items-center gap-3">
          <AppLogo size={44} />
          {/* "المستفيد" وليس "المستخدم": هذا هو الاسم المعتمد للنظام في سجل
              واحة (waha/src/config/apps.json)، وهو ما يظهر في شريط المنصة
              وبطاقة الصفحة الرئيسية. اسمان مختلفان لنفس النظام يعنيان أن
              المستخدم يقرأ اسماً في الشريط وآخر داخل الإطار. غيّرها في
              apps.json أولاً إن أُريد تغييرها. */}
          <div className="text-lg font-semibold tracking-tight text-brand">عدسة تجربة المستفيد</div>
        </Link>
      </div>
    </header>
  );
}
