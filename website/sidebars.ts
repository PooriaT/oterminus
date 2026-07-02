import type {SidebarsConfig} from '@docusaurus/plugin-content-docs';

const sidebars: SidebarsConfig = {
  docsSidebar: [
    {
      type: 'doc',
      id: 'index',
      label: 'Home',
    },
    {
      type: 'category',
      label: 'Product',
      items: [
        'product/what-is-oterminus',
        'product/user-guide',
        'product/shell-completion',
        'product/supported-workflows',
        'product/policy-modes',
      ],
    },
    {
      type: 'category',
      label: 'Architecture',
      items: [
        'architecture/overview',
        'architecture/request-lifecycle',
        'architecture/routing-and-planning',
        'architecture/validation-and-policy',
        'architecture/execution',
        'architecture/structured-rendering',
        'architecture/capability-system',
        'architecture/command-registry',
        'architecture/observability',
        'architecture/evals',
      ],
    },
    {
      type: 'category',
      label: 'Reference',
      items: [
        'reference/config',
        'reference/capability-map',
        'reference/command-families',
        'reference/audit-log-schema',
      ],
    },
    {
      type: 'category',
      label: 'Contributing',
      items: [
        'contributing',
        'dogfooding-playbook',
        'release',
        'adding-command-families',
      ],
    },
    {
      type: 'category',
      label: 'ADRs',
      items: [
        'adr/0001-capability-first-not-shell-first',
        'adr/0002-structured-first-planning',
        'adr/0003-router-before-planner',
        'adr/0004-network-diagnostics-boundary',
      ],
    },
  ],
};

export default sidebars;
