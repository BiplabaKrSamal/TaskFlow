from dataclasses import dataclass

from app.models import Project, Role, User


@dataclass
class Access:
    """The caller's standing in one project: who they are, which project, which role."""

    user: User
    project: Project
    role: Role

    @property
    def is_owner(self) -> bool:
        return self.role == Role.owner
