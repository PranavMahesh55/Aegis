import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./AppShell";
import { CommandCenterPage } from "../features/command-center/CommandCenterPage";
import { PipelineDetailPage } from "../features/pipelines/PipelineDetailPage";
import { IncidentQueuePage } from "../features/incidents/IncidentQueuePage";
import { IncidentWorkspacePage } from "../features/incidents/IncidentWorkspacePage";
import { ControlsPage } from "../features/controls/ControlsPage";

export function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<CommandCenterPage />} />
        <Route path="pipelines" element={<Navigate to="/pipelines/refund" replace />} />
        <Route path="pipelines/:pipelineId" element={<PipelineDetailPage />} />
        <Route path="incidents" element={<IncidentQueuePage />} />
        <Route path="incidents/:incidentId" element={<IncidentWorkspacePage />} />
        <Route path="controls" element={<ControlsPage />} />
        <Route path="controls/:controlId" element={<ControlsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}

