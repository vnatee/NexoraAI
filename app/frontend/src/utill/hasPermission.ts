interface HasPermissionOptions {
    permissions?: string[]; // permission ที่ user มี
    sys_permissions?: string[]; // permission ที่ user มีในระบบ
    requiredPermissions?: string[]; // permission ที่ต้องการ
    is_sys_admin?: boolean;
}

// export const hasPermission = ({ permissions = [], requiredPermissions = [], is_sys_admin = false }: HasPermissionOptions): boolean => {
//     if (is_sys_admin) return true;
//     if (requiredPermissions.length === 0) return true;

//     const normalize = (s: string) => s.trim().toLowerCase();

//     const permissionSet = new Set(permissions.map(normalize));

//     return requiredPermissions.some(p => permissionSet.has(normalize(p)));
// };

export const hasPermission = ({ permissions = [], sys_permissions = [], requiredPermissions = [], is_sys_admin = false }: HasPermissionOptions): boolean => {
    // 1. sys admin ผ่านหมด
    if (is_sys_admin) return true;

    // 2. ไม่ได้ require อะไรเลย
    if (requiredPermissions.length === 0) return true;

    const normalize = (s: string) => s.trim().toLowerCase();

    // รวม permission ทุกแหล่ง
    const allPermissions = [...permissions, ...sys_permissions].map(normalize);

    const permissionSet = new Set(allPermissions);

    // 3. มีอย่างน้อยหนึ่ง permission ที่ตรง
    return requiredPermissions.some(p => permissionSet.has(normalize(p)));
};
