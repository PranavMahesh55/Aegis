import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";

export const queryKeys = {
  status: ["status"] as const,
  pipelines: ["pipelines"] as const,
  pipeline: (id: string) => ["pipeline", id] as const,
  incidents: ["incidents"] as const,
  incident: (id: string) => ["incident", id] as const,
  graph: (id: string) => ["graph", id] as const,
  controls: ["controls"] as const,
  run: (id: string) => ["run", id] as const,
};

export function useStatus() {
  return useQuery({ queryKey: queryKeys.status, queryFn: api.status, refetchInterval: 15000 });
}

export function usePipelines() {
  return useQuery({ queryKey: queryKeys.pipelines, queryFn: api.pipelines });
}

export function usePipeline(id: string) {
  return useQuery({ queryKey: queryKeys.pipeline(id), queryFn: () => api.pipeline(id) });
}

export function useIncidents() {
  return useQuery({ queryKey: queryKeys.incidents, queryFn: api.incidents });
}

export function useIncident(id: string) {
  return useQuery({ queryKey: queryKeys.incident(id), queryFn: () => api.incident(id) });
}

export function useGraph(id: string) {
  return useQuery({ queryKey: queryKeys.graph(id), queryFn: () => api.graph(id) });
}

export function useControls() {
  return useQuery({ queryKey: queryKeys.controls, queryFn: api.controls });
}

export function useAgentRun(id: string | null) {
  return useQuery({
    queryKey: queryKeys.run(id ?? "none"),
    queryFn: () => api.run(id!),
    enabled: Boolean(id),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status && !["QUEUED", "RUNNING"].includes(status) ? false : 750;
    },
  });
}

export function useWorkflowMutation(
  mutation: (version: number) => Promise<Record<string, unknown>>,
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: mutation,
    onSuccess: async () => {
      await queryClient.invalidateQueries();
    },
  });
}

export function useResetMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.reset,
    onSuccess: async () => {
      await queryClient.invalidateQueries();
    },
  });
}

export function usePrimeMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.prime,
    onSuccess: async () => {
      await queryClient.invalidateQueries();
    },
  });
}
