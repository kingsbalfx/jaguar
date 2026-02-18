export const getServerSideProps = async (ctx) => {
  const { query } = ctx;
  const params = new URLSearchParams(query || {});
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return {
    redirect: {
      destination: `/register${suffix}`,
      permanent: false,
    },
  };
};

export default function AuthRegisterRedirect() {
  return null;
}
