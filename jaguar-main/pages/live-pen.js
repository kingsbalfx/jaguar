export async function getServerSideProps() {
  return {
    redirect: {
      destination: "/dashboard/live",
      permanent: false,
    },
  };
}

export default function LivePenRedirect() {
  return null;
}
