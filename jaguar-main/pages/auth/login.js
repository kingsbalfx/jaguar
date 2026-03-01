export const getServerSideProps = async (ctx) => {
  const { query } = ctx;
  const params = new URLSearchParams(query || {});
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return {
    redirect: {
      destination: `/login${suffix}`,
      permanent: false,
    },
  };
};

export default function AuthLoginRedirect() {
  return null;
}
