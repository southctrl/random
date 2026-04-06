"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { authClient } from "@/lib/auth-client"
import { BrandedBackground } from "@/components/branded-background"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card"
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table"
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import { Badge } from "@/components/ui/badge"
import { toast } from "sonner"

type User = {
    id: string
    email: string
    name: string | null
    emailVerified: boolean
    image: string | null
    role: string
    banned: boolean | null
    banReason: string | null
    createdAt: Date
    updatedAt: Date
}

type ListUsersResponse = {
    users: User[]
    total: number
}

export default function AdminDashboardPage() {
    const router = useRouter()
    const { data: sessionData, isPending: sessionPending } =
        authClient.useSession()
    const [isAdmin, setIsAdmin] = useState(false)
    const [isLoading, setIsLoading] = useState(true)
    const [users, setUsers] = useState<User[]>([])
    const [total, setTotal] = useState(0)
    const [page, setPage] = useState(1)
    const [search, setSearch] = useState("")
    const [selectedUser, setSelectedUser] = useState<User | null>(null)
    const [actionLoading, setActionLoading] = useState(false)

    const limit = 10

    useEffect(() => {
        if (sessionPending) return
        if (!sessionData?.session) {
            router.replace("/login")
            return
        }
        if (sessionData.user.role !== "admin") {
            router.replace("/dashboard")
            return
        }
        setIsAdmin(true)
        setIsLoading(false)
    }, [router, sessionData, sessionPending])

    const fetchUsers = async (
        pageNum: number = 1,
        searchTerm: string = search
    ) => {
        try {
            const result = await authClient.admin.listUsers({
                query: {
                    limit,
                    offset: (pageNum - 1) * limit,
                    searchValue: searchTerm || undefined,
                    searchField: "email",
                    searchOperator: "contains",
                },
            })
            if (result.data) {
                setUsers(result.data.users as unknown as User[])
                setTotal(result.data.total)
                setPage(pageNum)
            }
        } catch (error) {
            toast.error("Failed to fetch users")
        }
    }

    useEffect(() => {
        if (isAdmin) {
            fetchUsers()
        }
    }, [isAdmin])

    const handleSearch = (e: React.FormEvent) => {
        e.preventDefault()
        fetchUsers(1, search)
    }

    const handleSetRole = async (userId: string, role: string) => {
        setActionLoading(true)
        try {
            await authClient.admin.setRole({
                userId,
                role: role as "admin" | "user",
            })
            toast.success(`Role updated to ${role}`)
            fetchUsers(page, search)
            setSelectedUser(null)
        } catch {
            toast.error("Failed to update role")
        }
        setActionLoading(false)
    }

    const handleBanUser = async (userId: string, reason?: string) => {
        setActionLoading(true)
        try {
            await authClient.admin.banUser({ userId, banReason: reason })
            toast.success("User banned")
            fetchUsers(page, search)
            setSelectedUser(null)
        } catch {
            toast.error("Failed to ban user")
        }
        setActionLoading(false)
    }

    const handleUnbanUser = async (userId: string) => {
        setActionLoading(true)
        try {
            await authClient.admin.unbanUser({ userId })
            toast.success("User unbanned")
            fetchUsers(page, search)
            setSelectedUser(null)
        } catch {
            toast.error("Failed to unban user")
        }
        setActionLoading(false)
    }

    const handleRevokeAllSessions = async (userId: string) => {
        setActionLoading(true)
        try {
            await authClient.admin.revokeUserSessions({ userId })
            toast.success("All sessions revoked")
            setSelectedUser(null)
        } catch {
            toast.error("Failed to revoke sessions")
        }
        setActionLoading(false)
    }

    if (sessionPending || isLoading) {
        return (
            <div className="relative flex min-h-screen items-center justify-center overflow-hidden">
                <BrandedBackground />
                <p className="relative z-10 text-white/80">Loading…</p>
            </div>
        )
    }

    const totalPages = Math.ceil(total / limit)

    return (
        <div className="relative min-h-screen overflow-hidden">
            <BrandedBackground />
            <div className="relative z-10 container mx-auto px-4 py-8">
            <div className="mb-8">
                <h1 className="mb-2 font-sans text-3xl font-light text-white italic">
                    Admin Dashboard
                </h1>
                <p className="text-white/60">
                    Manage users and permissions
                </p>
            </div>

            <Card className="border-white/15 bg-black/35 text-white backdrop-blur-md">
                <CardHeader>
                    <CardTitle>Users</CardTitle>
                    <CardDescription>{total} total users</CardDescription>
                </CardHeader>
                <CardContent>
                    <form onSubmit={handleSearch} className="mb-4 flex gap-2">
                        <Input
                            placeholder="Search by email..."
                            value={search}
                            onChange={(e) => setSearch(e.target.value)}
                            className="max-w-sm"
                        />
                        <Button type="submit">Search</Button>
                        {search && (
                            <Button
                                type="button"
                                variant="ghost"
                                onClick={() => {
                                    setSearch("")
                                    fetchUsers(1, "")
                                }}
                            >
                                Clear
                            </Button>
                        )}
                    </form>

                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>Name</TableHead>
                                <TableHead>Email</TableHead>
                                <TableHead>Role</TableHead>
                                <TableHead>Status</TableHead>
                                <TableHead>Actions</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {users.map((user) => (
                                <TableRow key={user.id}>
                                    <TableCell className="font-medium">
                                        {user.name || "N/A"}
                                    </TableCell>
                                    <TableCell>{user.email}</TableCell>
                                    <TableCell>
                                        <Badge variant="outline">
                                            {user.role}
                                        </Badge>
                                    </TableCell>
                                    <TableCell>
                                        {user.banned ? (
                                            <Badge variant="destructive">
                                                Banned
                                            </Badge>
                                        ) : (
                                            <Badge variant="secondary">
                                                Active
                                            </Badge>
                                        )}
                                    </TableCell>
                                    <TableCell>
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            onClick={() =>
                                                setSelectedUser(user)
                                            }
                                        >
                                            Manage
                                        </Button>
                                    </TableCell>
                                </TableRow>
                            ))}
                            {users.length === 0 && (
                                <TableRow>
                                    <TableCell
                                        colSpan={5}
                                        className="text-center"
                                    >
                                        No users found
                                    </TableCell>
                                </TableRow>
                            )}
                        </TableBody>
                    </Table>

                    {totalPages > 1 && (
                        <div className="mt-4 flex items-center justify-between">
                            <p className="text-sm text-muted-foreground">
                                Page {page} of {totalPages}
                            </p>
                            <div className="flex gap-2">
                                <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={() => fetchUsers(page - 1)}
                                    disabled={page === 1}
                                >
                                    Previous
                                </Button>
                                <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={() => fetchUsers(page + 1)}
                                    disabled={page === totalPages}
                                >
                                    Next
                                </Button>
                            </div>
                        </div>
                    )}
                </CardContent>
            </Card>
            </div>

            <Dialog
                open={!!selectedUser}
                onOpenChange={() => setSelectedUser(null)}
            >
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Manage User</DialogTitle>
                        <DialogDescription>
                            {selectedUser?.email}
                        </DialogDescription>
                    </DialogHeader>
                    {selectedUser && (
                        <div className="space-y-4">
                            <div className="space-y-2">
                                <p className="text-sm font-medium">Role</p>
                                <div className="flex gap-2">
                                    <Button
                                        size="sm"
                                        variant={
                                            selectedUser.role === "admin"
                                                ? "default"
                                                : "outline"
                                        }
                                        onClick={() =>
                                            handleSetRole(
                                                selectedUser.id,
                                                "admin"
                                            )
                                        }
                                        disabled={actionLoading}
                                    >
                                        Admin
                                    </Button>
                                    <Button
                                        size="sm"
                                        variant={
                                            selectedUser.role === "user"
                                                ? "default"
                                                : "outline"
                                        }
                                        onClick={() =>
                                            handleSetRole(
                                                selectedUser.id,
                                                "user"
                                            )
                                        }
                                        disabled={actionLoading}
                                    >
                                        User
                                    </Button>
                                </div>
                            </div>

                            <div className="space-y-2">
                                <p className="text-sm font-medium">Status</p>
                                {selectedUser.banned ? (
                                    <Button
                                        size="sm"
                                        onClick={() =>
                                            handleUnbanUser(selectedUser.id)
                                        }
                                        disabled={actionLoading}
                                    >
                                        Unban User
                                    </Button>
                                ) : (
                                    <Button
                                        size="sm"
                                        variant="destructive"
                                        onClick={() =>
                                            handleBanUser(selectedUser.id)
                                        }
                                        disabled={actionLoading}
                                    >
                                        Ban User
                                    </Button>
                                )}
                            </div>

                            <div className="space-y-2">
                                <p className="text-sm font-medium">Sessions</p>
                                <Button
                                    size="sm"
                                    variant="outline"
                                    onClick={() =>
                                        handleRevokeAllSessions(selectedUser.id)
                                    }
                                    disabled={actionLoading}
                                >
                                    Revoke All Sessions
                                </Button>
                            </div>
                        </div>
                    )}
                </DialogContent>
            </Dialog>
        </div>
    )
}
