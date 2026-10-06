import { createContext, useContext, useEffect, useState } from "react";

const OrgContext = createContext(null);

const organizations = [
  {
    id: "acme-dev",
    name: "Acme Development",
    type: "Development",
    status: "Connected",
  },
  {
    id: "acme-uat",
    name: "Acme UAT",
    type: "UAT",
    status: "Connected",
  },
];

function OrgProvider({ children }) {
  const [organizationsList] = useState(organizations);

  const [activeOrgId, setActiveOrgId] = useState(() => {
    return (
      localStorage.getItem("activeOrgId") ||
      organizations[0]?.id ||
      null
    );
  });

  const activeOrg =
    organizationsList.find(
      (org) => org.id === activeOrgId
    ) || null;

  useEffect(() => {
    if (activeOrgId) {
      localStorage.setItem("activeOrgId", activeOrgId);
    }
  }, [activeOrgId]);

  function selectOrganization(orgId) {
    const exists = organizationsList.some(
      (org) => org.id === orgId
    );

    if (!exists) {
      return;
    }

    setActiveOrgId(orgId);
  }

  return (
    <OrgContext.Provider
      value={{
        organizations: organizationsList,
        activeOrg,
        activeOrgId,
        selectOrganization,
      }}
    >
      {children}
    </OrgContext.Provider>
  );
}

export function useOrg() {
  const context = useContext(OrgContext);

  if (!context) {
    throw new Error(
      "useOrg must be used inside OrgProvider"
    );
  }

  return context;
}

export default OrgProvider;