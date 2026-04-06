import { SignUp } from "@clerk/nextjs";

export default function SignUpPage() {
  return (
    <div className="ds-card ds-card--lg">
      <SignUp
        routing="path"
        path="/sign-up"
        signInUrl="/sign-in"
        fallbackRedirectUrl="/crawls"
        appearance={{
          elements: {
            rootBox: "mx-auto",
            card: "shadow-none border-0 bg-transparent",
            headerTitle: "font-soehne text-[var(--charcoal)]",
            headerSubtitle: "text-[var(--muted)]",
            formButtonPrimary:
              "bg-[var(--charcoal)] hover:bg-[var(--charcoal)] text-white text-[12px] font-medium rounded-[var(--radius-sm)]",
            formFieldInput:
              "border border-[var(--border)] rounded-[var(--radius-sm)] text-[13px]",
            footerActionLink: "text-[var(--charcoal)]",
          },
        }}
      />
    </div>
  );
}
