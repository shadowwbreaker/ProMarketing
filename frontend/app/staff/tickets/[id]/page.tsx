import { SupportAccess, TicketThread } from "@/components/SupportTickets";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <SupportAccess staff><TicketThread staff id={id} /></SupportAccess>;
}
