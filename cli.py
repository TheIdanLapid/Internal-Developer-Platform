import time
import typer
import requests
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

# הגדרת ה-CLI והקונסולה להדפסות מעוצבות
app = typer.Typer(help="IDP (Internal Developer Platform) CLI Tool")
console = Console()

API_BASE_URL = "http://127.0.0.1:8001"

@app.command()
def provision(
    service: str = typer.Option(..., "--service", "-s", help="The name of the service to provision (e.g., payment-api)"),
    env: str = typer.Option(..., "--env", "-e", help="Target environment (dev, qa, staging)"),
    ttl: str = typer.Option("2h", "--ttl", "-t", help="Time-To-Live for the environment (e.g., 2h, 4h)")
):
    """
    בקשה להקמת סביבה זמנית עבור שירות ספציפי.
    """
    payload = {
        "service_name": service,
        "environment": env,
        "ttl": ttl
    }

    try:
        # 1. שליחת בקשת ההקמה ל-Backend (FastAPI)
        response = requests.post(f"{API_BASE_URL}/provision", json=payload)
        response.raise_for_status()
        request_data = response.json()
        request_id = request_data["id"]
        
        console.print(f"[bold green]Provision request accepted![/bold green] Request ID: {request_id}")
        
    except requests.exceptions.RequestException as e:
        console.print(f"[bold red]Failed to connect to IDP API:[/bold red] {e}")
        if response is not None and response.status_code == 400:
            console.print(f"[red]Details: {response.json().get('detail')}[/red]")
        raise typer.Exit(code=1)

    # 2. מעקב (Polling) אחר סטטוס ההקמה עם תצוגה חזותית
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        task = progress.add_task(description=f"Provisioning {service} in {env} environment...", total=None)
        
        while True:
            try:
                status_response = requests.get(f"{API_BASE_URL}/provision/{request_id}")
                status_response.raise_for_status()
                current_status = status_response.json().get("status")
                
                if current_status == "COMPLETED":
                    progress.update(task, description="[bold green]Environment provisioned successfully![/bold green]")
                    break
                elif current_status == "FAILED":
                    progress.update(task, description="[bold red]Provisioning failed![/bold red]")
                    console.print("[bold red]Process failed during execution. Check logs.[/bold red]")
                    raise typer.Exit(code=1)
                
                # הסטטוס הוא PENDING או IN_PROGRESS - נמשיך להמתין
                time.sleep(5)
                
            except requests.exceptions.RequestException as e:
                progress.update(task, description="[bold red]Error checking status...[/bold red]")
                console.print(f"[bold red]Connection error while polling:[/bold red] {e}")
                time.sleep(5) # נסיון חוזר למרות השגיאה

    # 3. הצגת תוצאה סופית למפתח
    console.print(f"✅ [bold blue]Success![/bold blue] The environment for [bold]{service}[/bold] is ready.")
    console.print(f"👉 Environment: [bold]{env}[/bold]")
    console.print(f"⏱️  TTL: [bold]{ttl}[/bold]")
    console.print("🔗 URL: https://[generated-url-from-github-actions]/") 

if __name__ == "__main__":
    app()