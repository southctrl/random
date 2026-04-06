"use client"

import { AlertTriangle } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"

interface UnsavedChangesDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onConfirm: () => void
  onCancel: () => void
  title?: string
  description?: string
}

export function UnsavedChangesDialog({
  open,
  onOpenChange,
  onConfirm,
  onCancel,
  title = "You have unsaved changes",
  description = "You must save your changes before leaving this page. Would you like to discard your changes?",
}: UnsavedChangesDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent 
        className="border-white/10 bg-[#0d1117]/95 backdrop-blur-xl sm:max-w-[425px]"
        showCloseButton={false}
      >
        <DialogHeader>
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-amber-500/10">
            <AlertTriangle className="h-6 w-6 text-amber-500" />
          </div>
          <DialogTitle className="text-center text-white">{title}</DialogTitle>
          <DialogDescription className="text-center text-white/60">
            {description}
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-2 sm:flex-row sm:justify-center">
          <Button
            variant="outline"
            onClick={onCancel}
            className="w-full border-white/10 bg-white/5 text-white hover:bg-white/10 hover:text-white sm:w-auto"
          >
            Go Back & Save
          </Button>
          <Button
            onClick={onConfirm}
            className="w-full bg-red-500/80 text-white hover:bg-red-500 sm:w-auto"
          >
            Discard Changes
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
