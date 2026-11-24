import fs from 'node:fs';
import path from 'node:path';

const root = path.resolve(process.argv[2] || '.');

const read = (relativePath) =>
  fs.readFileSync(path.join(root, relativePath), 'utf8');

const write = (relativePath, content) =>
  fs.writeFileSync(path.join(root, relativePath), content, 'utf8');

const replaceOnce = (relativePath, expected, replacement) => {
  const source = read(relativePath);
  const first = source.indexOf(expected);
  if (first < 0) {
    throw new Error(`${relativePath}: expected GPUStack v2.3.1 source marker was not found`);
  }
  if (source.indexOf(expected, first + expected.length) >= 0) {
    throw new Error(`${relativePath}: source marker is not unique`);
  }
  write(
    relativePath,
    source.slice(0, first) + replacement + source.slice(first + expected.length)
  );
};

const replaceRange = (relativePath, startMarker, endMarker, replacement) => {
  const source = read(relativePath);
  const start = source.indexOf(startMarker);
  if (start < 0) {
    throw new Error(`${relativePath}: start marker was not found`);
  }
  const end = source.indexOf(endMarker, start + startMarker.length);
  if (end < 0) {
    throw new Error(`${relativePath}: end marker was not found`);
  }
  write(relativePath, source.slice(0, start) + replacement + source.slice(end));
};

replaceOnce(
  'config/config.ts',
  "  title: 'GPUStack',",
  "  title: 'InsightSphere Private AI Infrastructure',"
);

replaceOnce(
  'src/config/theme/constants.ts',
  "export const COLOR_PRIMARY = '#007BFF';",
  "export const COLOR_PRIMARY = '#0078D4';"
);

replaceOnce(
  'src/global.less',
  "@import url('./overrides.less');",
  "@import url('./overrides.less');\n@import './insightsphere-branding.less';"
);

replaceRange(
  'src/layouts/index.tsx',
  '              menuFooterRender={() => (',
  '              onCollapse={onCollapse}',
  `              menuFooterRender={() => (
                <div className="insightsphere-console-footer">
                  <Button
                    className="insightsphere-return-button"
                    size="small"
                    type="text"
                    title="Close this tab and return to InsightSphere"
                    aria-label="Back to InsightSphere"
                    onClick={() => window.close()}
                  >
                    <IconFont type="icon-home" className="font-size-16" />
                    {!collapsed && <span>Back to InsightSphere</span>}
                  </Button>
                  <Button
                    className="insightsphere-collapse-button"
                    size="small"
                    type="text"
                    title={collapsed ? 'Expand navigation' : 'Collapse navigation'}
                    aria-label={collapsed ? 'Expand navigation' : 'Collapse navigation'}
                    onClick={handleToggleCollapse}
                  >
                    <IconFont
                      type={collapsed ? 'icon-expand-left' : 'icon-expand-right'}
                      className="font-size-16"
                    />
                  </Button>
                </div>
              )}
`
);

replaceOnce(
  'src/components/footer/index.tsx',
  `              <CompanyWrapper>
                <span>&copy;</span>
                <span> {new Date().getFullYear()}</span>
                <Typography.Link
                  href="https://gpustack.ai"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {intl.formatMessage({ id: 'settings.company' })}
                </Typography.Link>
              </CompanyWrapper>`,
  `              <CompanyWrapper>
                <span>&copy; {new Date().getFullYear()} InsightSphere</span>
              </CompanyWrapper>
              <Divider orientation="vertical" />
              <Typography.Link
                href="https://gpustack.ai"
                target="_blank"
                rel="noopener noreferrer"
              >
                Powered by GPUStack
              </Typography.Link>`
);

console.log('Applied InsightSphere branding to GPUStack UI v2.3.1');
