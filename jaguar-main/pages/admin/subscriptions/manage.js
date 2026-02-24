import { useEffect } from "react";
import { useRouter } from "next/router";

export default function ManageRedirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/admin/subscriptions");
  }, [router]);
  return null;
}
