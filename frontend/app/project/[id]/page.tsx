import { WorkspaceClient } from "../../components/WorkspaceClient";

export default async function ProjectPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <main className="workspace-page">
      <WorkspaceClient key={id} routeId={id} />
    </main>
  );
}
