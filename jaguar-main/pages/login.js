// pages/login.js
import dynamic from "next/dynamic";

const LoginPage = dynamic(
  () => import("../components/LoginPage").then((mod) => mod.default),
  { ssr: false, loading: () => <div className="min-h-[calc(100vh-160px)]" /> }
);

export default function Login() {
  return <LoginPage />;
}
