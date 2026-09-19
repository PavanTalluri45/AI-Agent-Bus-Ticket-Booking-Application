import { Content } from "@/components/auth/content";
import { SignInCard } from "@/components/auth/sign-in-card";

export default function SignInPage() {
  return (
    <main className="flex h-svh flex-col md:h-auto md:min-h-svh md:flex-row md:items-center md:justify-center md:gap-24 md:p-4">
      <div className="flex h-1/2 items-center justify-center p-4 md:h-auto md:p-0">
        <Content />
      </div>
      <div className="flex h-1/2 items-center justify-center p-4 md:h-auto md:p-0">
        <SignInCard />
      </div>
    </main>
  );
}
