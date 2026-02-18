import dynamic from "next/dynamic";
const Uploader = dynamic(() => import("../../components/Uploader"), {
  ssr: false,
});
const AdminVideoPlayer = dynamic(
  () => import("../../components/AdminVideoPlayer"),
  { ssr: false },
);
export default function Content() {
  return (
    <div className="p-6 min-h-[calc(100vh-160px)]">
      <h2 className="text-2xl font-bold">Content Manager</h2>
      <p className="mt-2">
        Upload videos, audio, images, documents using Supabase Storage. Use the
        Admin Video Player to preview and polish.
      </p>
      <div className="mt-4 grid md:grid-cols-2 gap-4">
        <Uploader bucket="public" folder="videos" />
        <div>
          <Uploader bucket="public" folder="images" />
          <Uploader bucket="public" folder="docs" />
        </div>
      </div>
      <div className="mt-6">
        <AdminVideoPlayer bucket="public" initialPath="videos/" />
      </div>
    </div>
  );
}
