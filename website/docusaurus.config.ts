import {themes as prismThemes} from 'prism-react-renderer';
import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';

const config: Config = {
  title: 'OTerminus',
  tagline: 'Local, safety-first terminal assistance',
  url: 'https://pooriat.github.io',
  baseUrl: '/oterminus/',
  organizationName: 'PooriaT',
  projectName: 'oterminus',
  trailingSlash: false,

  onBrokenLinks: 'throw',

  i18n: {
    defaultLocale: 'en',
    locales: ['en'],
  },

  markdown: {
    mermaid: true,
    hooks: {
      onBrokenMarkdownLinks: 'throw',
    },
  },

  themes: ['@docusaurus/theme-mermaid'],

  presets: [
    [
      'classic',
      {
        docs: {
          routeBasePath: '/',
          sidebarPath: './sidebars.ts',
          editUrl: 'https://github.com/PooriaT/oterminus/tree/main/website/',
        },
        blog: false,
        theme: {
          customCss: './src/css/custom.css',
        },
      } satisfies Preset.Options,
    ],
  ],

  themeConfig: {
    navbar: {
      title: 'OTerminus',
      items: [
        {
          type: 'docSidebar',
          sidebarId: 'docsSidebar',
          position: 'left',
          label: 'Docs',
        },
        {
          href: 'https://github.com/PooriaT/oterminus',
          label: 'GitHub',
          position: 'right',
        },
      ],
    },
    footer: {
      style: 'dark',
      links: [
        {
          title: 'Project',
          items: [
            {
              label: 'GitHub',
              href: 'https://github.com/PooriaT/oterminus',
            },
            {
              label: 'MkDocs source',
              href: 'https://github.com/PooriaT/oterminus/tree/main/docs',
            },
          ],
        },
        {
          title: 'Package',
          items: [
            {
              label: 'PyPI',
              href: 'https://pypi.org/project/oterminus/',
            },
          ],
        },
      ],
      copyright: `Copyright ${new Date().getFullYear()} OTerminus contributors.`,
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
