const dashboardData = {
  organization: {
    name: "Acme Corp Production",
    environment: "Production",
    status: "Connected",
    apiVersion: "v60.0",
  },

  sync: {
    lastSynced: "2026-08-18 10:31:11",
  },

  health: {
    score: 92,
  },

  api: {
    used: 9243,
    limit: 15000,
    percentage: 62,
  },

  storage: {
    dataUsed: 8.6,
    dataLimit: 20,
    fileUsed: 12.1,
    fileLimit: 30,
  },

  users: {
    total: 482,
    active: 450,
    adoptionRate: 93,
  },

  licenses: {
    used: 5,
    total: 8,
  },

  metadata: {
    customObjects: 12,
    customFields: 126,
    activeFlows: 34,
    inactiveFlows: 6,
    apexClasses: 23,
    validationRules: 18,
  },

  scoreBreakdown: {
    apiHeadroom: 82,
    licenseAvailability: 38,
    storageHeadroom: 57,
    userAdoption: 93,
  },

  industryClouds: [],

  recentActivity: [
    {
      id: 1,
      type: "deployment",
      title: "Deployed Apex class OrderService to Production",
      user: "Priya Nair",
      time: "2h ago",
    },

    {
      id: 2,
      type: "migration",
      title: 'Migration job "Winter Metadata Sync" completed',
      user: "System",
      time: "5h ago",
    },

    {
      id: 3,
      type: "import",
      title: "Imported 4,200 Account records",
      user: "Arjun Mehta",
      time: "1d ago",
    },

    {
      id: 4,
      type: "warning",
      title: "API usage crossed 25% of daily limit",
      user: "System",
      time: "1d ago",
    },

    {
      id: 5,
      type: "user",
      title: "New license assigned to Sales Rep",
      user: "Riya Sharma",
      time: "2d ago",
    },
  ],

  // ============================
  // Salesforce Limits
  // ============================

  limits: {
    dailyApiRequests: {
      used: 9243,
      limit: 15000,
    },

    dailyAsyncApex: {
      used: 120,
      limit: 250,
    },

    workflowEmails: {
      used: 340,
      limit: 1000,
    },

    streamingApiClients: {
      used: 12,
      limit: 20,
    },

    singleEmail: {
      used: 45,
      limit: 100,
    },

    massEmail: {
      used: 2,
      limit: 5,
    },

    dashboardResults: {
      used: 34,
      limit: 100,
    },

    callouts: {
      used: 430,
      limit: 1000,
    },
  },

  // ============================
  // Scheduled Jobs
  // ============================

  scheduledJobs: {
    used: 3,
    limit: 10,
  },
};

export default dashboardData;