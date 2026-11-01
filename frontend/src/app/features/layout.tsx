import Sidebar from "@/components/Sidebar";

export default function FeaturesLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="mx-auto flex max-w-7xl">
      <Sidebar />
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}
