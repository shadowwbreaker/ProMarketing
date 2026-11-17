import { ArbitrationAccess } from "@/components/ArbitrationQueue";
import { StaffComplaint } from "@/components/StaffComplaint";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ArbitrationAccess><StaffComplaint id={id} /></ArbitrationAccess>;
}
